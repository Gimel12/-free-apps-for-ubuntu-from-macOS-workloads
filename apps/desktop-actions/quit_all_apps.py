#!/usr/bin/python3
"""Ask normal application windows to close, without killing their processes."""
import argparse
import os
import subprocess
import sys

from Xlib import X, display, error, protocol

EXCLUDED_CLASSES = {'ulauncher', 'gnome-shell', 'desktop_window', 'ding'}


def property_values(window, atom):
    prop = window.get_full_property(atom, X.AnyPropertyType)
    return [] if prop is None else list(prop.value)


def application_windows(connection):
    atom = connection.intern_atom
    normal_types = {atom('_NET_WM_WINDOW_TYPE_NORMAL'), atom('_NET_WM_WINDOW_TYPE_DIALOG')}
    result = []
    for window_id in property_values(connection.screen().root, atom('_NET_CLIENT_LIST')):
        window = connection.create_resource_object('window', int(window_id))
        try:
            types = set(property_values(window, atom('_NET_WM_WINDOW_TYPE')))
            if types and not types.intersection(normal_types):
                continue
            classes = tuple(window.get_wm_class() or ())
            if any(part.lower() in EXCLUDED_CLASSES for part in classes):
                continue
            if window.get_attributes().override_redirect:
                continue
            parent = window.get_wm_transient_for()
            result.append((window, parent.id if parent else None, classes))
        except (error.XError, error.BadWindow):
            continue
    # Let the parent handle its own save/confirmation dialogs. Never immediately
    # close newly created dialogs by rescanning while requests are being handled.
    ids = {window.id for window, _, _ in result}
    return [(window, classes) for window, parent, classes in result if parent not in ids]


def request_close(connection, window):
    event = protocol.event.ClientMessage(
        window=window.id,
        client_type=connection.intern_atom('_NET_CLOSE_WINDOW'),
        data=(32, [X.CurrentTime, 2, 0, 0, 0]),
    )
    connection.screen().root.send_event(event,
        event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)


def notify(message):
    subprocess.run(['/usr/bin/notify-send', '--app-name=Desktop Actions',
                    'Quit All Apps', message], check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='List targets without closing anything')
    args = parser.parse_args()
    if os.environ.get('XDG_SESSION_TYPE') == 'wayland':
        notify('This command is configured for your X11 desktop session.')
        return 1
    connection = display.Display()
    try:
        windows = application_windows(connection)
        if args.dry_run:
            for window, classes in windows:
                print(f'0x{window.id:x}  {" / ".join(classes) or "Application"}')
            print(f'{len(windows)} application windows; no close requests sent.')
            return 0
        if not windows:
            notify('There are no application windows to close.')
            return 0
        notify('Closing open app windows. Save or cancel any prompts that appear.')
        for window, _ in windows:
            try:
                request_close(connection, window)
            except error.XError:
                pass
        connection.sync()
        return 0
    finally:
        connection.close()


if __name__ == '__main__':
    sys.exit(main())
