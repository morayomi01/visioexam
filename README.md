# VisioExam — Personalized Multilingual Examination System for Visually Impaired Candidates
# Adekunle Ajasin University · Computer Science · Group 1

## Overview

VisioExam is a prototype self-voicing, keyboard-navigable desktop examination system for visually impaired candidates in Nigeria. It includes native TTS and accessibility APIs. Its kiosk controls are best-effort application controls, not a substitute for a managed OS kiosk account or secure examination workstation.

## Supported Platforms

- Windows 10/11 (64-bit)
- Ubuntu 20.04 LTS+ (64-bit)

## Prerequisites

System-level packages:

```bash
# Ubuntu / Debian
sudo apt install espeak-ng libespeak-ng-dev python3-louis

# Windows
# Install eSpeak-NG from https://github.com/espeak-ng/espeak-ng/releases
```

The production database requires SQLCipher support and a strong passphrase in
`VISIOEXAM_DB_KEY`. The app reads `KEY=VALUE` entries from the project-root
`.env` file at startup; variables already set in the process environment take
precedence. Add the database key alongside any API settings, for example:

```dotenv
VISIOEXAM_DB_KEY=replace-this-with-your-database-passphrase
```

Use the same passphrase on every launch for an existing encrypted database.
If the original key is lost, the encrypted database cannot be opened; do not
replace it with a new value unless starting a new database. The Python binding
also needs a compatible native SQLCipher library. The app stops at startup if
SQLCipher or the key is unavailable; it does not silently create a plaintext
production database. Existing plaintext databases are not migrated
automatically. Back up the data and plan an explicit SQLCipher migration before
enabling this requirement on an existing installation.

For local UI evaluation only, set `VISIOEXAM_ALLOW_PLAINTEXT_DB=1` to explicitly
open a plaintext SQLite database. Do not use this setting for real candidate or
exam data.

## Installation

```bash
git clone <repo>
cd visioexam
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

## Windows release build

- Client instructions: [docs/CLIENT_GUIDE.md](docs/CLIENT_GUIDE.md)
- Owner publishing steps: [docs/OWNER_GITHUB_GUIDE.md](docs/OWNER_GITHUB_GUIDE.md)

Run `build_release.ps1` from PowerShell on a 64-bit Windows machine after
installing the project requirements in `venv`. It creates
`release/VisioExam-portable.zip`; if Inno Setup 6 is installed, it also creates
`release/VisioExam-Setup.exe`. Give the owner the installer (or the complete
portable ZIP), never just `VisioExam.exe`. The installer is per-user and does
not require administrator rights.

On the first launch, VisioExam creates its encrypted database and a random
database key protected by Windows DPAPI for that Windows account. The database,
settings, logs, and model downloads are kept under
`%LOCALAPPDATA%/VisioExam`, outside the installed program folder. Do not copy
the developer's `.env`, database, or `.salt` file into the release.

Yoruba and Hausa speech models download from Hugging Face when first needed.
Igbo speech downloads its YarnGPT model and a WavTokenizer checkpoint (about
1.3 GB) on first use. The owner needs internet access and enough free disk
space for these downloads; subsequent use reads the local cache.

On first launch the setup wizard runs automatically.

### Reset administrator credentials

Close VisioExam, then run this from the project folder:

```powershell
.\venv\Scripts\python.exe reset_admin.py
```

The utility uses the database key in `.env`, updates the selected administrator
account (or creates the first account if none exists), and asks for the new
password without displaying it. The password must be 12–72 UTF-8 bytes.

### Question language and speech

During an exam, VisioExam reads each question and its choices exactly as they
were entered by the administrator. A candidate's language selection chooses
the speech engine; it does not translate the question text. For example, to
present a question in Yoruba, import the Yoruba wording and select Yoruba for
  the candidate. If English text is spoken with a Yoruba voice, pronunciation may
  not sound natural.
  Common equation notation in questions and choices is expanded for speech
  (for example, `x²` is spoken as “x squared” and `a/b` as “a over b”). The
  displayed text remains unchanged. Math wording currently uses conventional
  English terms; localized classroom math terminology needs review by a fluent
  teacher before it can be treated as reliable.

Only multiple-choice items are delivered in the exam. CSV and QTI imports skip
items that do not have at least two answer choices and a correct choice.

Yoruba and Hausa TTS models are fetched when first selected. Igbo TTS also needs
the YarnGPT helper under `vendor/yarngpt` and downloads a roughly 1.3 GB audio
tokenizer on first use. Complete one connected setup run for every language
before using `VISIOEXAM_OFFLINE=1`; offline mode uses cached model files only.

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
visioexam/
├── main.py                          Entry point
├── requirements.txt
├── core/
│   ├── database.py                  SQLite (+ optional SQLCipher) DB layer
│   ├── profile_manager.py           Candidate profile CRUD
│   ├── tts_engine.py                eSpeak-NG TTS wrapper (en/yo/ha/ig)
│   ├── braille_display.py           liblouis + HID Braille output
│   └── exam_engine.py               Question delivery, timer, auto-save
├── security/
│   ├── encryption.py                AES-256-GCM response encryption
│   ├── audit_logger.py              HMAC-signed tamper-evident audit log
│   ├── kiosk.py                     OS-level kiosk lockdown (Win/Linux)
│   └── admin_auth.py                bcrypt admin authentication
├── admin/
│   └── admin_module.py              Question upload, candidate reg, results export
├── ui/
│   ├── app.py                       PyQt6 application shell
│   └── screens/
│       ├── wizard.py                First-time setup wizard
│       ├── login.py                 Candidate login
│       ├── exam.py                  Exam delivery screen
│       ├── settings.py              Candidate preferences
│       ├── admin_login.py           Admin login
│       └── admin_panel.py           Admin management panel
├── resources/
│   └── themes/
│       └── themes.py                Light / Dark / HCYOB theme tokens
└── tests/
    └── test_visioexam.py            pytest unit + integration tests
```

## Architecture

Five-module layered design:

| Module | Key Files | Technologies |
|--------|-----------|--------------|
| Presentation | ui/app.py, ui/screens/ | PyQt6, WCAG 2.1 AA |
| TTS & Output | core/tts_engine.py, core/braille_display.py | eSpeak-NG, liblouis, HID |
| Exam Engine | core/exam_engine.py | Python, SQLite |
| Security | security/ | AES-256-GCM, bcrypt, OS APIs |
| Admin | admin/ | CSV/QTI 3.0, bcrypt |

## Security Notes

- Candidate responses: AES-256-GCM encrypted before writing to disk
- Database: SQLCipher required for production use; set `VISIOEXAM_DB_KEY` to a
  strong secret that is stored outside the project directory
- Admin passwords: bcrypt, cost factor 12
- Audit log: HMAC-SHA256 per entry; append-only
- Windows kiosk hook blocks common task-switching shortcuts where supported;
  Windows still reserves Ctrl+Alt+Del. Linux controls are best-effort. Use an
  OS-managed kiosk account for high-stakes exams.
- Braille support requires liblouis, a compatible HID Braille display, and a
  device-specific protocol. The current generic HID writer is not verified for
  every display model.

## Known Limitations

- eSpeak-NG Yoruba, Hausa, and Igbo voice quality depends on community voice data; accuracy may be below the 95% target for some question types
- Braille translation tables for Nigerian language Braille codes are not standardized; UEB is used as a base
- SQLCipher must be installed for the production database. AES-GCM response
  encryption alone does not encrypt profiles, questions, or audit metadata.
- Offline TTS requires pre-cached weights and the YarnGPT helper files. The app
  loads each neural voice on first use rather than loading all large models at
  startup.

## Group 1

Oloruntola · Fabiyi · Shittu · Kayode · Adelegan · Fadumo  
Supervisor: Dr. (Mrs.) E. O. Aliyu  
Department of Computer Science, Adekunle Ajasin University
