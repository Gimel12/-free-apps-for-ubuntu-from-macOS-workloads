# Free apps for Ubuntu from macOS workloads

Two free, local desktop apps for moving everyday writing from macOS to Ubuntu. Your notes and snippets belong to you: no account, subscription, or cloud service is required.

| App | Familiar macOS workflow | What you get |
| --- | --- | --- |
| [Notes](apps/notes/README.md) | Bear / Apple Notes | White-and-blue glass-style notebook, rich Markdown, highlighted code blocks, tags, search, autosave, and backups |
| [Snippets](apps/snippets/README.md) | TextExpander | Searchable text library, abbreviations, fill-in templates, groups, favorites, and TextExpander CSV import |

These are independent alternatives. They are not affiliated with Apple, Bear, or TextExpander. Apple Notes/iCloud sync and full TextExpander macro compatibility are not included.

## Install on another Ubuntu computer

Tested on **Ubuntu 24.04 LTS, x86_64**. Install from your normal desktop account. Internet access and sudo access are needed to install dependencies.

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/Gimel12/-free-apps-for-ubuntu-from-macOS-workloads.git ubuntu-apps
cd ubuntu-apps
./install.sh
```

The installer sets up both apps, installs Ubuntu packages, creates a dedicated Python environment for Notes, and registers desktop launchers. Search for **Notes** or **Snippets** in Ubuntu's app menu or in Ulauncher if you already use it. You can delete the cloned source folder after installation; the apps run from your user application directory.

**Snippets' global expansion and Ctrl+. picker require an X11 desktop session.** On Ubuntu 24.04, select your user at the login screen, use the gear menu, and choose **Ubuntu on Xorg** before signing in. Open **AutoKey** once after installation to enable shortcuts; subsequent logins start it automatically. Notes works independently of AutoKey. Other Ubuntu releases and ARM machines have not been tested.

```bash
./install.sh --notes         # Notes only
./install.sh --snippets      # Snippets only
./install.sh --no-autostart  # Manage AutoKey startup yourself
./install.sh --dry-run       # Preview commands
python3 scripts/doctor.py    # Check your installation
```

Quit AutoKey before installing or updating Snippets. The installer preserves your databases and backs up existing Snippets and AutoKey configuration. `--skip-system` skips apt when the dependencies are already installed. `--no-autostart` does not disable an existing startup entry.

## Bring your libraries with you

The repository contains **application code only**. Your personal notes, snippets, exports, and databases are excluded.

On the old computer, save your edits, then run:

```bash
python3 scripts/transfer.py backup ~/Documents/ubuntu-apps-backup.zip
```

Copy that private archive to the new computer. Install the apps there, close Notes, Snippets, the picker, and AutoKey, then run:

```bash
python3 scripts/transfer.py restore ~/Documents/ubuntu-apps-backup.zip
```

Restore replaces the installed libraries with the archived libraries, preserves the previous databases, and rebuilds typed abbreviations. Restart AutoKey afterward. See [migration and recovery](docs/MIGRATION.md) for details.

## Updates

Close both apps and AutoKey, back up your libraries, then run from your clone:

```bash
git pull --ff-only
./install.sh
```

Application code and personal libraries live in separate folders. Reinstalling does not reset your notes or snippets.

## Repository layout

```text
apps/notes/       Native Qt notebook and its tests
apps/snippets/    Native GTK snippet library and its tests
scripts/         Backup, restore, and installation checks
tests/           Transfer and clean-install checks
docs/            Migration and development guides
install.sh       Shared Ubuntu installer
```

[Development and testing](docs/DEVELOPMENT.md) · [Notes guide](apps/notes/README.md) · [Snippets guide](apps/snippets/README.md) · [MIT license](LICENSE) · [Third-party dependencies](THIRD_PARTY.md)
