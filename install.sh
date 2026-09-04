#!/usr/bin/env bash
# Install applications for the invoking desktop user. Use sudo only for apt.
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APPS=all
SKIP_SYSTEM=0
AUTOSTART=1
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --all) APPS=all ;;
        --notes) APPS=notes ;;
        --snippets) APPS=snippets ;;
        --skip-system) SKIP_SYSTEM=1 ;;
        --no-autostart) AUTOSTART=0 ;;
        --dry-run) DRY_RUN=1 ;;
        -h|--help)
            echo 'Usage: ./install.sh [--all|--notes|--snippets] [--skip-system] [--no-autostart] [--dry-run]'
            echo 'Run as your desktop user, not with sudo. Default: both apps, AutoKey starts at next login.'
            exit 0 ;;
        *) echo "Unknown argument: $arg" >&2; exit 2 ;;
    esac
done
if [[ "$EUID" -eq 0 ]]; then
    echo 'Run this installer as your normal desktop user, without sudo.' >&2
    exit 1
fi
run() {
    if [[ "$DRY_RUN" -eq 1 ]]; then printf 'Would run:'; printf ' %q' "$@"; printf '\n'; else "$@"; fi
}
if [[ "$APPS" != notes && "$DRY_RUN" -eq 0 ]]; then
    if pgrep -u "$(id -u)" -f '^(/usr/bin/python3 )?/usr/bin/autokey-(gtk|qt)( |$)' >/dev/null; then
        echo 'Quit AutoKey from its tray menu, then rerun the installer. Your shortcuts will be preserved.' >&2
        exit 1
    fi
fi
if [[ "$SKIP_SYSTEM" -eq 0 ]]; then
    if ! command -v apt-get >/dev/null; then
        echo 'This installer uses Ubuntu apt. Install the documented dependencies manually and use --skip-system.' >&2
        exit 1
    fi
    PACKAGES=(python3 python3-venv desktop-file-utils)
    if [[ "$APPS" != snippets ]]; then
        PACKAGES+=(libegl1 libgl1 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4
                   libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0)
    fi
    if [[ "$APPS" != notes ]]; then
        PACKAGES+=(python3-gi gir1.2-gtk-3.0 autokey-gtk xdotool)
    fi
    run sudo apt-get update
    run sudo apt-get install -y "${PACKAGES[@]}"
fi

if [[ "$APPS" != snippets ]]; then
    NOTES_BASE="${XDG_DATA_HOME:-$HOME/.local/share}/blue-notes"
    run /usr/bin/python3 -m venv "$NOTES_BASE/venv"
    run "$NOTES_BASE/venv/bin/python" -m pip install --disable-pip-version-check -r "$ROOT_DIR/apps/notes/requirements.lock"
    run "$NOTES_BASE/venv/bin/python" "$ROOT_DIR/apps/notes/install.py"
fi
if [[ "$APPS" != notes ]]; then
    SNIPPET_ARGS=()
    if [[ "$AUTOSTART" -eq 0 ]]; then SNIPPET_ARGS+=(--no-autostart); fi
    run /usr/bin/python3 "$ROOT_DIR/apps/snippets/install.py" "${SNIPPET_ARGS[@]}"
    if [[ "${XDG_SESSION_TYPE:-}" == wayland ]]; then
        echo 'Snippets is installed, but global expansion needs X11. At login choose Ubuntu on Xorg.'
    fi
fi
echo 'Installation finished. Search for Notes or Snippets in your application launcher or Ulauncher.'
if [[ "$APPS" != notes ]]; then
    echo 'Open AutoKey once (or sign out and back in) to enable Ctrl+. and typed abbreviations.'
fi
