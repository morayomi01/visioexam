# Owner's GitHub Publishing Guide

This guide separates the **source repository** from the **downloadable app**.
Keep source files in the repository. Publish the Windows ZIP or installer as a
GitHub Release asset so users can find and download the ready-to-run build.

## Before you publish

1. Confirm the owner has granted you **Write** access to their GitHub
   repository, or ask them to create the repository and invite your account.
2. Decide whether the source repository should be private or public. Use
   private visibility if the owner has not approved public source publication.
3. Review `.gitignore`. It excludes `.env`, the local database and its backups,
   logs, build outputs, and candidate/result CSVs. Do not remove these ignores
   to make GitHub "look complete".
4. Use `candidates.template.csv` as the blank import template. Never publish
   actual candidate lists or result exports.
5. Search the files you intend to upload for API keys, passwords, private
   student data, and database files. If a secret was committed previously,
   deleting the file is not enough: revoke/rotate it and remove it from the
   repository history before making the repository public.
6. Review the model licenses and the contents of `vendor/yarngpt` with the
   project owner before distributing or publishing. The Igbo model/helper has
   license conditions; bundling its code and publishing the app should be
   approved by the owner.
7. Complete a first-install check on a clean Windows account, including first
   administrator creation, candidate setup, an exam, and each required speech
   language. Do not describe the build as ready for clients until that works.

## Put the source code in the owner's repository

The current project folder is not yet a Git repository and has no configured
GitHub remote. Create an empty repository in the owner's GitHub account first:

1. Sign in to GitHub as the owner (or use an account with write access).
2. Select **New repository**.
3. Set a repository name, such as `visioexam`.
4. Choose **Private** or **Public** according to the owner's decision.
5. For an existing project folder, leave **Add a README**, **Add .gitignore**,
   and **Choose a license** unchecked so the new remote starts empty.
6. Select **Create repository** and copy its HTTPS URL, for example
   `https://github.com/OWNER/visioexam.git`.

Open PowerShell in `C:\Users\DELL\Documents\Projects\visioexam`. Inspect
the staged contents before committing:

```powershell
git init
git branch -M main
git status --short --ignored
git add .
git status --short
```

In the second status output, confirm there are no `.env`, `data/*.db*`, `.salt`,
`candidates.csv`, `results.csv`, `venv`, `dist`, `build`, `release`, or log
files. If any appear under staged changes, unstage them before proceeding.
If Git warns that `vendor/yarngpt` is an embedded repository, stop before
committing: a plain `git add .` may record only a pointer instead of the helper
files. Ask the owner whether to publish it as a Git submodule or include a
reviewed vendor snapshot, and verify that a fresh clone still contains the
helper files needed by `build_release.ps1`.

```powershell
git diff --cached --name-only
git diff --cached --check
git commit -m "Prepare VisioExam Windows release"
git remote add origin https://github.com/OWNER/visioexam.git
git push -u origin main
```

Replace `OWNER` and the repository name with the URL copied from GitHub. GitHub
will ask you to authenticate; use the owner's approved sign-in method. Do not
put a password or personal access token into the remote URL or a source file.

If the owner already created a non-empty repository or the project already
has Git history on another machine, stop before `git init`/push and coordinate
with the owner. Clone that repository and transfer reviewed project files
instead of overwriting its history.

## Publish the Windows app as a GitHub Release

The app build is separate from the source-code push. On a 64-bit Windows build
PC, use the approved project environment and run:

```powershell
cd C:\Users\DELL\Documents\Projects\visioexam
.\build_release.ps1
```

The script builds the app, writes `release\VisioExam-portable.zip`, and creates
`release\VisioExam-Setup.exe` when Inno Setup 6 is installed. This project
currently has the ZIP; the installer requires Inno Setup 6. Test the exact
asset on a clean Windows account before uploading it.

In the GitHub repository:

1. Open **Releases** and choose **Draft a new release**.
2. Create a tag such as `v1.0.0` and use a clear release title.
3. Add short release notes with supported Windows versions, first-run internet
   requirements, the Igbo download size, and the known limitations.
4. Drag `release\VisioExam-portable.zip` into the release asset area. Add
   `VisioExam-Setup.exe` only after you have built and tested it.
5. Check the uploaded filenames and release notes, then publish the release.
6. Send clients the release's **download page**, not a link to the source
   repository's **Code → Download ZIP** option.

GitHub's automatically generated source ZIP is not the installable app. The
app download is the manually attached `VisioExam-portable.zip` or installer.

## Updating the app later

For each approved update, commit and push the source changes, build and test a
new package, create a new version tag (for example `v1.0.1`), and attach the new
package to a new GitHub Release. Tell clients whether the update keeps their
existing local data. Never upload a client's database to the public release.

## Official GitHub references

- [Add locally hosted code to GitHub](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)
- [Manage releases in a repository](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [GitHub's guidance on avoiding secret commits](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)
