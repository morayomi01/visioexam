# VisioExam Client Guide

## Welcome

VisioExam is a Windows desktop examination application designed to make
multiple-choice exams more accessible. It can read questions and answer
choices aloud, and it includes visual and keyboard accessibility settings.

This guide explains how to install the Windows package, prepare an exam, and
support candidates. Your institution should appoint an administrator to
manage candidate records, questions, exam IDs, and results.

## What you need

- A 64-bit Windows 10 or Windows 11 computer.
- Internet access for the first download of each speech model you use.
- Free disk space for the app and model cache. Igbo speech uses a large
  one-time download (the WavTokenizer checkpoint is about 1.3 GB).
- Headphones or speakers. A compatible refreshable Braille display can also be
  used when configured.
- Candidate IDs and an exam prepared by your institution's administrator.

## Install VisioExam

### If you received `VisioExam-Setup.exe`

1. Download the installer from your institution's official GitHub release page.
2. In File Explorer, open **Downloads** and double-click `VisioExam-Setup.exe`.
3. If Windows asks whether to allow the app, verify that the file came from
   your institution before choosing **Run anyway**. If you are unsure, stop and
   contact your administrator.
4. Follow the setup prompts. The app installs for your Windows account and
   does not need administrator permission.
5. Start VisioExam from the Start menu or desktop shortcut.

### If you received `VisioExam-portable.zip`

1. Right-click the ZIP and choose **Extract All**. Do not try to run the app
   from inside the compressed ZIP.
2. Open the extracted `VisioExam` folder.
3. Double-click `VisioExam.exe` inside that folder. Keep all other files and
   folders beside it; the EXE depends on them.
4. For convenience, right-click `VisioExam.exe` and choose **Show more
   options → Send to → Desktop (create shortcut)**.

Do not download or share only `VisioExam.exe`. The full folder is required.

## First launch and speech models

On first launch, follow the accessibility setup wizard. You can change these
preferences later. The application stores its local database, settings, and
logs in your Windows user's `%LOCALAPPDATA%\VisioExam` folder. Each Windows
account has its own local data.

The speech models download when a language is first used. Keep the computer
connected to the internet and leave VisioExam open while a model downloads.
Yoruba and Hausa models are downloaded from Hugging Face. Igbo needs the
YarnGPT model plus the approximately 1.3 GB WavTokenizer checkpoint. The
download is cached, so it is not normally repeated on later runs. Make sure
there is enough disk space before selecting Igbo speech.

If speech setup fails, check internet access and disk space, restart VisioExam,
and try again. If the problem continues, send your administrator the time of
the failure and the log file at `%LOCALAPPDATA%\VisioExam\logs\visioexam.log`.
Do not send database files or passwords.

## Administrator: prepare an examination

The administrator should complete these steps before candidates arrive:

1. Open the **Administrator** sign-in screen from the app.
2. Sign in with the administrator account issued by your institution.
3. In the dashboard, create an exam. Enter a clear title and the time limit.
4. Select the saved exam and use **Copy selected exam ID**. Save that ID in
   the institution's secure exam records; candidates need the matching exam.
5. Import questions from a CSV or QTI 3.0 XML file. VisioExam delivers
   multiple-choice questions only. Each item needs at least two options and
   one correct option. Check imported question counts and wording before the
   exam.
6. Add candidates individually or import a CSV based on
   `candidates.template.csv`. The required headers are `id`, `full_name`,
   `language`, and `modality`. Use unique candidate IDs and verify them with
   the candidate list before exam day.
7. Confirm the exam, question set, time limit, candidate list, audio output,
   and any Braille hardware using a practice run before a real exam.

Question text is read as entered; selecting Yoruba, Hausa, or Igbo does not
translate an English question. Prepare the question wording in the language
students should hear. Common equation notation is expanded for speech, while
the visible question stays unchanged.

## Candidate: take an examination

1. Put on headphones if provided. On the login page, choose a language and
   accessibility options that work for you.
2. Enter the candidate ID given by the administrator, then choose **Enter
   System** or **Voice-Assisted Login**.
3. Follow the spoken and on-screen instructions. Use the displayed answer
   choices to select your response. This exam interface is multiple-choice;
   it does not ask you to type free-form answers.
4. Use the exam navigation controls to move between questions and review your
   choices. Submit when finished, or follow the on-screen timer instructions.
5. Tell the invigilator immediately if audio, keyboard navigation, or Braille
   output stops working.

## Results and data

Only authorized administrators should open the results area or export results.
Exports contain candidate-identifying information and must be stored and
shared using the institution's approved process. Each computer keeps its own
local database; this package does not synchronize records between computers
or across Wi-Fi.

## Troubleshooting

| Problem | What to do |
|---|---|
| Windows says the app is unrecognized | Check that you downloaded it from the official institutional release. Ask the administrator to confirm the file before proceeding. |
| Candidate ID is not accepted | Check spelling and capitalization with the administrator; the candidate must already be registered on this computer's database. |
| No speech or speech in the wrong language | Check the selected language and speakers/headphones. The language selection chooses speech; it does not translate question text. |
| First use of a language takes a long time | Keep the internet connection active and wait for the model download to finish. Igbo has a particularly large download. |
| Exam or questions are missing | Ask the administrator to confirm that the exam and candidates were set up on this same computer. |
| App will not close normally | Press **Esc** to leave full-screen mode, then close the app using the window close button. |

## Important note for the institution

Before distributing a fresh installation, confirm that the installed build
provides a way to create the first administrator account and that the local
administrator has been created. If you were not given administrator
credentials, contact the institution's VisioExam deployment contact; do not
try default passwords. The project build being prepared currently needs this
first-account setup checked before it can be treated as a turnkey client
release.
