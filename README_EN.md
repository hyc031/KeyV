[简体中文](README.md) | **English**

<div align="center">

# KeyV

**KeyV, your local vault.**

A local-first, fully offline desktop vault for your API keys, passwords, and server credentials.

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=flat)
![Offline](https://img.shields.io/badge/offline-100%25-44CC11?style=flat)
![Version](https://img.shields.io/badge/version-1.2.0-6366F1?style=flat)

</div>

## ✨ Features

- **Groups** — Create, rename, and delete custom groups (e.g. *LLM APIs*, *Servers*, *Social accounts*); records in a deleted group fall back to *Ungrouped*
- **Card-based records** — Each record holds name / group / account / secret·password / tags / URL / note; hover a card to edit or delete it, or select it and use the toolbar / `Delete` key
- **Global search & tags** — Real-time, cross-group search over name / account / URL / note / tags / group name (case-insensitive); multiple tags separated by commas (Chinese or English), sidebar counts follow the active query
- **One-click copy with auto-clear** — Hover a card to copy the secret, use the icon next to the account to copy it; the button flips to a green "✓ Copied"; **the clipboard is cleared automatically after 30 seconds** (your own clipboard changes in the meantime are never overwritten, and any leftover is cleaned up on exit)
- **Encrypted backup** — Export a password-protected `.sab` file from the ⚙ menu (PBKDF2 × 200,000 rounds + AES-256-GCM); before importing you get a preview and can choose *merge (dedupe)* or *replace all*
- **Masked secrets** — Secrets render as dots by default with a per-card eye toggle; the ⚙ menu reveals them globally
- **Minimal light UI** — Top bar + group sidebar + card list, styled after Linear / Raycast (10px radius, soft shadows, 150ms transitions, illustrated empty states)
- **Local & offline** — Everything lives in a local SQLite file; no network, no browser window, no telemetry

## 🚀 Quick Start

**Requirements**: Windows 10 / 11 (Edge WebView2 runtime is preinstalled) · Python 3.8+

```bash
git clone https://github.com/<username>/KeyV.git
cd KeyV
pip install -r requirements.txt
python main.py
```

### Build a single-file exe

```bash
build_exe.bat
```

This produces `dist/StoreApp.exe` — a single, console-free file you can double-click to run, no installation needed.
Rebuilding never touches your existing `data/` files.

## 📖 Usage

**Layout**

- **Top bar**: logo & name · rounded global search field (with the `Ctrl K` hint) · ⚙ settings menu
- **Sidebar**: All Records / Ungrouped / your custom groups, each with a count badge; "New group" at the bottom
- **Main area**: toolbar (Edit / Delete / New record) above the card list; each card shows a colored group avatar, name, account, tag pills, and the masked secret

**Keyboard shortcuts**

| Shortcut | Action |
| --- | --- |
| `Ctrl/Cmd + K` · `Ctrl/Cmd + F` | Focus the search field |
| `Ctrl/Cmd + N` | New record |
| `Delete` | Delete the selected card |
| `Esc` | Clear search / close dialog |

**Settings menu (⚙)**: reveal secrets (global toggle) · export encrypted backup · import backup · version & database path

## 💾 Data & Backup

**Where data is stored**

| Run mode | Data file location |
| --- | --- |
| `python main.py` | `<project dir>/data/storeapp.db` |
| `StoreApp.exe` | `<exe dir>/data/storeapp.db` |

**The `.sab` backup file**

- Layout: `MAGIC | salt(16B) | nonce(12B) | AES-256-GCM(ciphertext)`, extension `.sab`
- The password is supplied by you at export time and **is stored nowhere; a forgotten password makes the backup unrecoverable**
- A wrong password or a tampered file fails with a clear error — dirty data is never imported
- Before importing, the backup contents (groups / records / export time) are shown so you can pick *merge* or *replace*

## 🔒 Security Notice

The database currently uses **plaintext with lightweight obfuscation** by design (a storage-encryption scheme is documented in [docs/master-password-design.md](docs/master-password-design.md) but is **not enabled**):

- The `secret` field is obfuscated (XOR + Base64) before it is written, so a casual viewer of the file sees nothing useful
- **Obfuscation is not encryption**: the obfuscation key ships with the source and can be reversed; anyone holding `storeapp.db` plus the source can recover every secret
- Therefore, **never upload the `data/` directory to any repository or cloud drive**
- Conversely, `.sab` backups are real encryption (AES-256-GCM); with a strong password they are safe to copy to a USB drive or cloud storage

## 🗂 Project Structure

```
KeyV/
├── main.py                        # Entry point: pywebview opens a native window on the bundled UI
├── build_exe.bat                  # One-shot packaging script (bundles web assets & WebView2 deps)
├── requirements.txt               # pywebview + cryptography (runtime) + pyinstaller (build)
├── docs/
│   └── master-password-design.md  # Storage-encryption design doc (not enabled)
├── data/storeapp.db               # Data file (created at runtime, ignored by .gitignore)
└── storeapp/
    ├── __init__.py
    ├── db.py                      # SQLite data layer: group/record CRUD, search, migrations
    ├── obfuscate.py               # Lightweight obfuscation for the secret field
    ├── backup.py                  # .sab backup I/O (PBKDF2 + AES-256-GCM)
    ├── api.py                     # API exposed to the UI (pywebview js_api, errors as {ok:false})
    ├── clipboard.py               # Windows clipboard read/write + 30s auto-clear (ctypes)
    └── web/                       # UI assets (read directly in dev, bundled into the exe)
        ├── index.html             # Page skeleton: top bar / sidebar / list / modals
        ├── app.css                # Design system: #FAFAFA bg, indigo #6366F1, 10px radius, 150ms
        └── app.js                 # Rendering & interactions (vanilla JS, no build step)
```

## 🛠 Tech Stack

| Layer | Technology |
| --- | --- |
| Window | [pywebview](https://pywebview.flowrl.com/) (native window) rendering offline via Edge WebView2 |
| Frontend | Vanilla HTML / CSS / JavaScript — no framework, no build chain |
| Storage | SQLite (Python built-in `sqlite3`) + lightweight secret obfuscation |
| Crypto | [cryptography](https://cryptography.io/): PBKDF2-HMAC-SHA256 (200,000 rounds) + AES-256-GCM |
| Clipboard | Win32 API via `ctypes`, cleared 30 seconds after copying |
| Packaging | [PyInstaller](https://pyinstaller.org/) (single file, no console) |
