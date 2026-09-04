import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {QuickToggle, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

const NAME = 'com.bizon.FanControl';
export default class QuietMode extends Extension {
    enable() {
        this._cancel = new Gio.Cancellable();
        this._busy = false;
        this._indicator = new SystemIndicator();
        this._toggle = new QuickToggle({title: 'Quiet Mode', subtitle: 'Light tasks',
            iconName: 'audio-volume-muted-symbolic', toggleMode: true});
        this._toggle.connect('clicked', () => this._set(this._toggle.checked));
        this._indicator.quickSettingsItems.push(this._toggle);
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => {
            this._sync();
            return GLib.SOURCE_CONTINUE;
        });
        this._sync();
    }

    _call(method) {
        return new Promise((resolve, reject) => Gio.DBus.system.call(NAME,
            '/com/bizon/FanControl', NAME, method, null, null,
            Gio.DBusCallFlags.NONE, 15000, this._cancel, (bus, result) => {
                try { resolve(bus.call_finish(result)?.deep_unpack()); }
                catch (error) { reject(error); }
            }));
    }

    async _sync() {
        if (this._busy || this._refreshing || !this._toggle)
            return;
        this._refreshing = true;
        try {
            const [json] = await this._call('Status');
            if (!this._toggle || this._busy)
                return;
            const status = JSON.parse(json);
            this._toggle.checked = status.mode === 'quiet';
            this._toggle.subtitle = this._toggle.checked ? 'Low power · Quiet fans' : 'Light tasks';
            this._toggle.reactive = true;
        } catch (_) {
            if (this._toggle) {
                this._toggle.subtitle = 'Unavailable';
                this._toggle.reactive = false;
            }
        } finally { this._refreshing = false; }
    }

    async _set(enabled) {
        if (this._busy)
            return;
        this._busy = true;
        this._toggle.reactive = false;
        try {
            if (enabled) {
                const process = Gio.Subprocess.new(
                    ['/usr/bin/systemctl', '--user', 'stop', 'bizon-game-mode.service'],
                    Gio.SubprocessFlags.STDERR_PIPE);
                await new Promise((resolve, reject) => process.wait_check_async(this._cancel,
                    (source, result) => {
                        try { source.wait_check_finish(result); resolve(); }
                        catch (error) { reject(error); }
                    }));
            }
            await this._call(enabled ? 'QuietOn' : 'QuietOff');
        } catch (error) {
            if (!this._cancel?.is_cancelled())
                Main.notifyError('Quiet Mode', error.message);
        } finally {
            this._busy = false;
            this._sync();
        }
    }

    disable() {
        this._cancel?.cancel();
        if (this._timer)
            GLib.Source.remove(this._timer);
        this._toggle?.destroy();
        this._indicator?.destroy();
        this._toggle = null;
        this._indicator = null;
        this._timer = 0;
    }
}
