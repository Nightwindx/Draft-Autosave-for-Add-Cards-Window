# Draft Autosave for Add Cards Window
# -----------------------------------
# Features:
# - Autosaves Add dialog fields + tags every AUTOSAVE_INTERVAL_MS
# - Keeps separate drafts per note type
# - Stores a timestamp for each draft
# - Ignores/cleans drafts older than MAX_AGE_SECONDS
# - Silently restores drafts when you reopen Add (same note type)
# - Clears the draft for that note type when:
#     * a note is successfully added, OR
#     * the Add window is actually closed (eg, via "Discard current input?")
#
# Goal: protect against crashes/power loss, while respecting explicit discards.

from __future__ import annotations

import json
import os
import time
from typing import Dict, Any, List, Optional

from aqt import mw
from aqt.addcards import AddCards
from aqt.gui_hooks import add_cards_did_init, add_cards_did_add_note
from aqt.qt import QTimer, QCloseEvent


# ---- Configuration --------------------------------------------------------

# How often to autosave (milliseconds)
AUTOSAVE_INTERVAL_MS = 5000  # 5000 = 5 seconds

# How long drafts are considered "fresh" (seconds)
# Example: 48 hours = 48 * 60 * 60
MAX_AGE_SECONDS = 48 * 60 * 60


# ---- Helpers: paths & basic utilities ------------------------------------

def _backup_path() -> str:
    """Path for the autosave file (per profile)."""
    profile_dir = mw.pm.profileFolder()
    return os.path.join(profile_dir, "add_cards_autosave.json")


def _now_ts() -> float:
    """Current time as a Unix timestamp (UTC)."""
    return time.time()


# ---- Helpers: note & fields ----------------------------------------------

def _note_type_name(note) -> str:
    """Get a human-readable notetype name, compatible with older/newer Anki."""
    if note is None:
        return ""
    try:
        nt = note.note_type()  # newer Anki
    except AttributeError:
        nt = note.model()      # older Anki
    return nt.get("name", "")


def _extract_fields(note) -> List[str]:
    """Return the list of field values in order."""
    fields: List[str] = []
    for _, value in note.items():
        fields.append(value)
    return fields


def _apply_fields(note, fields: List[str]) -> None:
    """Set field contents back onto a note."""
    for i, (field_name, _old_val) in enumerate(note.items()):
        if i < len(fields):
            note[field_name] = fields[i]


# ---- Helpers: JSON read/write (multi-notetype) ---------------------------

def _load_all_backups() -> Dict[str, Any]:
    """
    Load the full backup mapping from disk.

    Structure:
    {
      "Basic": {
          "last_saved": 1710000000.0,
          "fields": [...],
          "tags": [...]
      },
      "Cloze": {
          ...
      }
    }
    """
    path = _backup_path()
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        # If file is corrupted, just ignore it.
        return {}


def _save_all_backups(data: Dict[str, Any]) -> None:
    """Write the full backup mapping to disk."""
    path = _backup_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        # Fail silently – losing the backup is better than crashing Anki.
        pass


def _prune_old_backups(backups: Dict[str, Any]) -> Dict[str, Any]:
    """Remove entries older than MAX_AGE_SECONDS."""
    now = _now_ts()
    cleaned: Dict[str, Any] = {}
    for nt_name, entry in backups.items():
        try:
            last_saved = float(entry.get("last_saved", 0))
        except Exception:
            continue
        if now - last_saved <= MAX_AGE_SECONDS:
            cleaned[nt_name] = entry
    return cleaned


def _load_backup_for_notetype(nt_name: str) -> Optional[Dict[str, Any]]:
    """Load backup for a specific note type, respecting age limit."""
    if not nt_name:
        return None

    backups = _load_all_backups()
    backups = _prune_old_backups(backups)

    # Clean up old entries on disk immediately
    _save_all_backups(backups)

    entry = backups.get(nt_name)
    if not entry:
        return None

    try:
        last_saved = float(entry.get("last_saved", 0))
    except Exception:
        return None

    if _now_ts() - last_saved > MAX_AGE_SECONDS:
        # Too old; ignore and clean
        backups.pop(nt_name, None)
        _save_all_backups(backups)
        return None

    return entry


def _save_backup_for_notetype(nt_name: str, fields: List[str], tags: List[str]) -> None:
    """Save a backup entry for a specific note type."""
    if not nt_name:
        return

    backups = _load_all_backups()
    backups = _prune_old_backups(backups)

    backups[nt_name] = {
        "last_saved": _now_ts(),
        "fields": fields,
        "tags": tags,
    }

    _save_all_backups(backups)


def _clear_backup_for_notetype(nt_name: str) -> None:
    """Remove backup for a specific note type; delete file if empty."""
    if not nt_name:
        return
    backups = _load_all_backups()
    if nt_name in backups:
        backups.pop(nt_name, None)
        if backups:
            _save_all_backups(backups)
        else:
            # No backups left; remove file
            path = _backup_path()
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            except Exception:
                pass


def _clear_all_backups() -> None:
    """Remove all backups."""
    path = _backup_path()
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except Exception:
        pass


# ---- Core logic: restore + autosave --------------------------------------

def _restore_into_add_dialog(add_cards: AddCards) -> None:
    """
    If there is a backup that matches this note type, restore it silently.
    """
    editor = add_cards.editor
    note = editor.note
    nt_name = _note_type_name(note)
    if not nt_name:
        return

    backup = _load_backup_for_notetype(nt_name)
    if not backup:
        return

    fields = backup.get("fields")
    if not isinstance(fields, list):
        return

    tags = backup.get("tags")

    # Apply fields and tags
    _apply_fields(note, fields)
    if isinstance(tags, list):
        try:
            note.tags = tags
        except Exception:
            pass

    # Refresh UI
    try:
        editor.loadNoteKeepingFocus()
    except Exception:
        try:
            editor.loadNote()
        except Exception:
            pass


def _start_autosave_timer(add_cards: AddCards) -> None:
    """Start a QTimer attached to the Add dialog that periodically saves the note."""
    editor = add_cards.editor

    # Track the last note type name we autosaved for this dialog,
    # so that when the dialog is closed, we know what to clear.
    add_cards._draft_autosave_last_nt_name = ""  # type: ignore[attr-defined]

    def do_autosave() -> None:
        note = editor.note
        if note is None:
            return

        nt_name = _note_type_name(note)
        if not nt_name:
            return

        # Remember last note type we autosaved for this AddCards instance
        add_cards._draft_autosave_last_nt_name = nt_name  # type: ignore[attr-defined]

        fields = _extract_fields(note)
        tags = list(getattr(note, "tags", []))

        _save_backup_for_notetype(nt_name, fields, tags)

    timer = QTimer(add_cards)
    timer.setInterval(AUTOSAVE_INTERVAL_MS)
    timer.timeout.connect(do_autosave)
    timer.start()

    # Keep a reference so it stays alive with the dialog
    add_cards._draft_autosave_timer = timer  # type: ignore[attr-defined]


# ---- Patch AddCards.closeEvent to clear draft on real close --------------

def _patch_close_event_for_drafts() -> None:
    """Wrap AddCards.closeEvent so that when the Add window actually closes,
    the draft for the last autosaved note type is cleared.
    """
    if getattr(AddCards, "_draft_autosave_close_patched", False):
        return

    original_close_event = getattr(AddCards, "closeEvent", None)
    if original_close_event is None:
        return

    def wrapped_close_event(self: AddCards, evt: QCloseEvent) -> None:
        # When the Add window is really closing (e.g. Discard confirmed),
        # this method is called. Crashes/power loss never call this.
        try:
            nt_name = getattr(self, "_draft_autosave_last_nt_name", "")
        except Exception:
            nt_name = ""

        try:
            if nt_name:
                _clear_backup_for_notetype(nt_name)
            else:
                # As a fallback, clear all drafts
                _clear_all_backups()
        except Exception:
            # Don't let errors here crash Anki
            pass

        # Call the original closeEvent implementation
        original_close_event(self, evt)

    AddCards.closeEvent = wrapped_close_event  # type: ignore[assignment]
    AddCards._draft_autosave_close_patched = True


_patch_close_event_for_drafts()


# ---- Hooks ---------------------------------------------------------------

def on_add_cards_did_init(add_cards: AddCards) -> None:
    """Called when the Add Cards dialog is opened."""
    _restore_into_add_dialog(add_cards)
    _start_autosave_timer(add_cards)


def on_add_cards_did_add_note(note) -> None:
    """Called when a note is successfully added from Add dialog."""
    # Once a card is actually added, we assume that draft is no longer needed
    nt_name = _note_type_name(note)
    if nt_name:
        _clear_backup_for_notetype(nt_name)


add_cards_did_init.append(on_add_cards_did_init)
add_cards_did_add_note.append(on_add_cards_did_add_note)
