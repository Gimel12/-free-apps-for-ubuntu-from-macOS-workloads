import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {QuickToggle, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

const UNIT = 'bizon-game-mode.service';

export default class GameModeToggle extends Extension {
    enable() {
        this._cancel = new Gio.Cancellable();
        this._busy = false;
        this._indicator = new SystemIndicator();
        this._toggle = new QuickToggle({
            title: 'Game Mode',
            subtitle: 'Loading…',
            iconName: 'applications-games-symbolic',
            toggleMode: true,
            reactive: false,
        });
        this._toggle.connect('clicked', () => this._setEnabled(this._toggle.checked));
        this._indicator.quickSettingsItems.push(this._toggle);
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
        const cancel = this._cancel;
        // systemd emits unit updates only after this bus client subscribes.
        // The session connection is shared with Shell extensions, so do not
        // unsubscribe it when this extension is disabled.
        Gio.DBus.session.call('org.freedesktop.systemd1', '/org/freedesktop/systemd1',
            'org.freedesktop.systemd1.Manager', 'Subscribe', null, null,
            Gio.DBusCallFlags.NONE, 5000, cancel, (connection, result) => {
                try {
                    connection.call_finish(result);
                } catch (error) {
                    const name = Gio.DBusError.get_remote_error(error);
                    if (!cancel.is_cancelled() &&
                        name !== 'org.freedesktop.systemd1.AlreadySubscribed')
                        this._error(error);
                }
            });
        Gio.DBus.session.call('org.freedesktop.systemd1', '/org/freedesktop/systemd1',
            'org.freedesktop.systemd1.Manager', 'LoadUnit', new GLib.Variant('(s)', [UNIT]),
            new GLib.VariantType('(o)'), Gio.DBusCallFlags.NONE, 5000, cancel,
            (connection, result) => {
                try {
                    const [path] = connection.call_finish(result).deep_unpack();
                    if (cancel.is_cancelled())
                        return;
                    const proxy = new Gio.DBusProxy({
                        g_connection: Gio.DBus.session,
                        g_name: 'org.freedesktop.systemd1',
                        g_object_path: path,
                        g_interface_name: 'org.freedesktop.systemd1.Unit',
                    });
                    proxy.init_async(GLib.PRIORITY_DEFAULT, cancel, (source, ready) => {
                        try {
                            source.init_finish(ready);
                            if (cancel.is_cancelled())
                                return;
                            this._proxy = proxy;
                            this._changed = proxy.connect('g-properties-changed', () => this._sync());
                            this._sync();
                        } catch (error) {
                            if (!cancel.is_cancelled())
                                this._error(error);
                        }
                    });
                } catch (error) {
                    if (!cancel.is_cancelled())
                        this._error(error);
                }
            });
    }

    _sync() {
        if (!this._toggle || !this._proxy)
            return;
        const state = this._proxy.get_cached_property('ActiveState')?.deep_unpack() ?? 'inactive';
        this._toggle.checked = state === 'active' || state === 'activating';
        this._toggle.subtitle = ({active: 'Performance', activating: 'Starting…',
            deactivating: 'Stopping…', failed: 'Could not start'})[state] ?? 'Off';
        this._toggle.reactive = !this._busy && !['activating', 'deactivating'].includes(state);
    }

    _setEnabled(enabled) {
        if (this._busy)
            return;
        this._busy = true;
        this._toggle.reactive = false;
        const cancel = this._cancel;
        try {
            const process = Gio.Subprocess.new(
                ['systemctl', '--user', enabled ? 'start' : 'stop', UNIT],
                Gio.SubprocessFlags.STDOUT_SILENCE | Gio.SubprocessFlags.STDERR_PIPE);
            process.communicate_utf8_async(null, cancel, (source, result) => {
                try {
                    const [, , stderr] = source.communicate_utf8_finish(result);
                    if (!source.get_successful())
                        throw new Error(stderr.trim() || 'Could not change Game Mode');
                } catch (error) {
                    if (!cancel.is_cancelled())
                        this._error(error);
                } finally {
                    if (!cancel.is_cancelled()) {
                        this._busy = false;
                        this._sync();
                    }
                }
            });
        } catch (error) {
            this._busy = false;
            this._error(error);
            this._sync();
        }
    }

    _error(error) {
        if (this._toggle) {
            this._toggle.subtitle = 'Unavailable';
            Main.notifyError('Game Mode', error.message);
        }
    }

    disable() {
        this._cancel?.cancel();
        if (this._proxy && this._changed)
            this._proxy.disconnect(this._changed);
        this._toggle?.destroy();
        this._indicator?.destroy();
        this._toggle = null;
        this._indicator = null;
        this._proxy = null;
        this._changed = null;
        this._cancel = null;
        // The user service survives a Shell refresh; stop it using the toggle.
    }
}
