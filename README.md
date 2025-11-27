

This add-on automatically saves the contents of the **Add Cards** window every few seconds, so you never lose work if:

* Anki crashes
* Your laptop runs out of power
* You accidentally close the Add window
* Another add-on misbehaves
* The OS freezes or reboots

If you reopen the Add window with the **same note type**, your draft will be restored automatically.

---

## 🚀 **Features**

### ✔ **Automatic autosave**

* Saves every *N* seconds (default: 5 seconds).
* Saves all fields + tags.
* Very lightweight, no noticeable performance impact.

### ✔ **Separate drafts for each note type**

Each note type (Basic, Cloze, Custom types) stores its own independent draft.

### ✔ **Timestamp-based protection**

* Each draft has a `last_saved` timestamp.
* Drafts older than a configurable age (default: **48 hours**) are ignored and cleaned automatically.
* Prevents old drafts from “coming back from the dead.”

### ✔ **Safe behavior**

* Draft is deleted only after the note is successfully added.
* Never touches Anki’s database directly.
* Writes only tiny JSON files → very low overhead.

---

## 🛠 **Installation**

1. Open Anki.
2. Go to: **Tools → Add-ons → Open Add-ons Folder**
3. Create a folder, for example:

```
addons21/
  add_cards_autosave/
    __init__.py
    README.md
```

4. Place `__init__.py` inside that folder.
5. Restart Anki.

---

## ⚙️ **Configuration**

Inside `__init__.py`, you can customize:

### **Autosave interval**

```
AUTOSAVE_INTERVAL_MS = 5000    # 5 seconds
```

### **Maximum draft age**

```
MAX_AGE_SECONDS = 48 * 60 * 60   # 48 hours
```

### **Where drafts are stored**

Drafts are saved in:

```
<your Anki profile folder>/add_cards_autosave.json
```

Each draft is stored by note type:

```json
{
  "Basic": {
    "last_saved": 1732690000.123,
    "fields": ["Front", "Back"],
    "tags": ["tag1"]
  },
  "Cloze": { ... }
}
```

---

## 🔒 **When drafts are restored**

A draft is restored **only if all are true**:

* The note type matches
* Draft is not older than `MAX_AGE_SECONDS`
* JSON entry contains valid fields

Otherwise, the draft is ignored.

---

## 🧹 **When drafts are deleted**

A draft is removed **only when a note is successfully added or discarded (Add window closed manually)**.

Drafts are *not* deleted when:

* You switch note types
* Anki crashes
* The OS shuts down unexpectedly

This ensures your work is always recoverable.

---

## ❗ Compatibility

* Works with Anki **2.1.60+**
* Should work with earlier versions with minimal changes
* Compatible with most editor add-ons
* Light enough for slow/older machines

If you find a conflict with another add-on, open an issue or report the add-on name.

---

## 🧩 Why this add-on is helpful

The Add Cards window does **not** autosave by default.
If you’ve ever:

* Spent 10–20 minutes writing a detailed card
* Experienced a crash or laptop power loss
* Reopened Anki to find your card completely gone

…this add-on solves that forever.
It gives Anki a “draft safety net” that many users wish it had built in.

---


## 🙋 FAQ

**Q: Will autosaving every 5 seconds slow down my PC?**
**A:** No. Each autosave writes a tiny JSON file (1–5 KB).
CPU and disk impact are effectively zero.

**Q: Does it autosave images / LaTeX?**
**A:** It autosaves *whatever is in the fields* — including image references and LaTeX code.

**Q: Does it work with multi-line fields / HTML?**
**A:** Yes, everything is stored as plain text in JSON.

**Q: How do I test the add-on?**
**A:** Write notes in the Add Card Window, next open task manager, then right-click on the Python processes running under "Apps" and click "End Task", after that relaunch Anki, and finally reopen the Add cards window. The draft should be restored.

---

## 🧪 Testing notes

Test scenarios to confirm full behavior:

| Test                      | Expected result               |
| ------------------------- | ----------------------------- |
| Close Add without saving  | Draft preserved               |
| Crash Anki                | Draft preserved               |
| Power loss                | Draft preserved               |
| Change note type          | Draft *not* restored          |
| Add note successfully     | Draft deleted                 |
| Autorestore after restart | Fields restored automatically |

---

## 📬 Contact

Feel free to open an issue or request enhancements.
This add-on was designed to prevent one of the most common sources of lost work in Anki.

