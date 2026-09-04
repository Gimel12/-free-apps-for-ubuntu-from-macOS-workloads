import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {QuickSlider, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

const NAME = 'com.bizon.FanControl';
const PATH = '/com/bizon/FanControl';

export default class FanControl extends Extension {
    enable() {
        this._cancel = new Gio.Cancellable();
        this._syncing = false;
        this._ready = false;
        this._dragging = false;
        this._busy = false;
        this._manual = false;
        this._pending = 0;
        this._indicator = new SystemIndicator();
        this._slider = new QuickSlider({
            gicon: Gio.icon_new_for_string(`${this.path}/fan-symbolic.svg`),
            iconLabel: 'Fans — click for automatic cooling',
            iconReactive: true,
            menuEnabled: true,
        });
        this._slider.slider.accessible_name = 'Fan speed, 30 to 100 percent';
        this._label = new St.Label({text: '…', y_align: Clutter.ActorAlign.CENTER,
            style: 'min-width: 3.5em; text-align: right;'});
        this._slider.get_child().insert_child_at_index(this._label, 2);
        this._slider.menu.setHeader('preferences-system-symbolic', 'Cooling fans',
            'Both fans • 30–100%');
        this._automatic = this._slider.menu.addAction('Automatic cooling', () => this._auto());
        this._slider.menu.addAction('Open Z13 Fan Control', () => {
            Gio.Subprocess.new(['/usr/bin/gtk-launch', 'com.bizon.Z13FanControl'], Gio.SubprocessFlags.NONE);
            Main.panel.statusArea.quickSettings.menu.close();
        });
        this._rpm = new PopupMenu.PopupMenuItem('Reading fan speeds…', {reactive: false});
        this._temperature = new PopupMenu.PopupMenuItem('', {reactive: false});
        this._slider.menu.addMenuItem(this._rpm);
        this._slider.menu.addMenuItem(this._temperature);
        this._slider.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());
        this._thermal = new PopupMenu.PopupMenuItem(
            'Thermal boost above 75°C · Full speed at 85°C', {reactive: false});
        this._slider.menu.addMenuItem(this._thermal);
        this._slider.connect('icon-clicked', () => this._auto());
        this._slider.slider.connect('drag-begin', () => { this._dragging = true; });
        this._slider.slider.connect('drag-end', () => {
            this._dragging = false;
            this._schedule();
        });
        this._slider.slider.connect('notify::value', () => {
            if (this._syncing || !this._ready)
                return;
            this._label.text = `${this._percent()}%`;
            if (!this._dragging)
                this._schedule();
        });
        this._indicator.quickSettingsItems.push(this._slider);
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator, 2);
        this._menuSignal = Main.panel.statusArea.quickSettings.menu.connect('open-state-changed',
            (_menu, open) => { if (open) this._refresh(); });
        this._timer = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 5, () => {
            if (this._manual)
                this._call('KeepAlive').catch(error => this._error(error));
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
        this._refresh();
    }

    _percent() {
        return Math.round(30 + this._slider.slider.value * 70);
    }

    _call(method, parameters = null) {
        const cancel = this._cancel;
        return new Promise((resolve, reject) => {
            Gio.DBus.system.call(NAME, PATH, NAME, method, parameters, null,
                Gio.DBusCallFlags.NONE, 5000, cancel, (bus, result) => {
                    try { resolve(bus.call_finish(result)?.deep_unpack()); }
                    catch (error) { reject(error); }
                });
        });
    }

    _schedule() {
        if (!this._ready)
            return;
        if (this._pending)
            GLib.Source.remove(this._pending);
        this._pending = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 250, () => {
            this._pending = 0;
            if (this._busy) {
                this._schedule();
                return GLib.SOURCE_REMOVE;
            }
            this._set(this._percent());
            return GLib.SOURCE_REMOVE;
        });
    }

    async _set(percent) {
        this._busy = true;
        try {
            await this._call('SetSpeed', new GLib.Variant('(u)', [percent]));
            this._manual = true;
        } catch (error) {
            this._error(error, true);
        } finally {
            this._busy = false;
            this._refresh();
        }
    }

    async _auto() {
        if (!this._cancel)
            return;
        if (this._pending) {
            GLib.Source.remove(this._pending);
            this._pending = 0;
        }
        this._busy = true;
        try {
            await this._call('Automatic');
            this._manual = false;
        } catch (error) {
            this._error(error, true);
        } finally {
            this._busy = false;
            this._refresh();
        }
    }

    async _refresh() {
        if (!this._cancel || this._refreshing || this._busy || this._pending || this._dragging)
            return;
        this._refreshing = true;
        try {
            const [json] = await this._call('Status');
            if (!this._slider || this._busy || this._pending || this._dragging)
                return;
            const status = JSON.parse(json);
            this._manual = status.mode === 'manual';
            this._ready = true;
            this._syncing = true;
            this._slider.slider.value = this._manual ? (status.speed - 30) / 70 : 0;
            this._syncing = false;
            this._label.text = status.mode === 'quiet' ? 'Quiet' : status.mode === 'curve' ? 'Curve' : this._manual ? `${status.speed}%` : 'Auto';
            this._slider.slider.reactive = !['quiet', 'curve'].includes(status.mode);
            this._slider.slider.accessible_name = status.profile
                ? `${status.profile.name}; edit in Z13 Fan Control` : this._manual
                    ? `Fan speed ${status.speed} percent` : 'Automatic fans; move to set 30 to 100 percent';
            this._thermal.label.text = status.profile
                ? 'Custom curve · Full cooling at 95°C'
                : 'Thermal boost above 75°C · Full speed at 85°C';
            this._rpm.label.text = `CPU ${status.rpm[0] ?? '—'} RPM  ·  GPU ${status.rpm[1] ?? '—'} RPM`;
            this._temperature.label.text = status.temperature === null
                ? 'Temperature unavailable' : `CPU temperature ${Math.round(status.temperature)}°C`;
            this._automatic.setOrnament(status.mode === 'automatic' ? PopupMenu.Ornament.CHECK : PopupMenu.Ornament.NONE);
        } catch (error) {
            this._error(error);
        } finally {
            this._refreshing = false;
        }
    }

    _error(error, notify = false) {
        if (!this._cancel || this._cancel.is_cancelled())
            return;
        this._ready = false;
        this._label.text = '—';
        if (notify)
            Main.notifyError('Fan control', error.message);
    }

    disable() {
        if (this._timer)
            GLib.Source.remove(this._timer);
        if (this._pending)
            GLib.Source.remove(this._pending);
        if (this._menuSignal)
            Main.panel.statusArea.quickSettings.menu.disconnect(this._menuSignal);
        this._cancel?.cancel();
        // Release manual control on disable. The service also has a 45s lease.
        if (this._manual)
            Gio.DBus.system.call(NAME, PATH, NAME, 'Automatic', null, null,
            Gio.DBusCallFlags.NONE, 5000, null, (bus, result) => {
                try { bus.call_finish(result); } catch (_) { /* Service restores on exit. */ }
            });
        this._slider?.destroy();
        this._indicator?.destroy();
        this._slider = null;
        this._indicator = null;
        this._cancel = null;
        this._timer = 0;
        this._pending = 0;
        this._menuSignal = 0;
    }
}
