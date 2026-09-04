import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {QuickToggle, SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

const KEY = 'screen-keyboard-enabled';

export default class ScreenKeyboard extends Extension {
    enable() {
        this._showSource = 0;
        this._settings = new Gio.Settings({schema_id: 'org.gnome.desktop.a11y.applications'});
        this._indicator = new SystemIndicator();
        this._toggle = new QuickToggle({
            title: 'Screen Keyboard',
            iconName: 'input-keyboard-symbolic',
            toggleMode: true,
        });
        this._changed = this._settings.connect(`changed::${KEY}`, () => this._sync());
        this._toggle.connect('clicked', () => {
            const enabled = this._toggle.checked;
            if (this._showSource) {
                GLib.Source.remove(this._showSource);
                this._showSource = 0;
            }
            if (!this._settings.set_boolean(KEY, enabled)) {
                this._sync();
                Main.notifyError('Screen Keyboard', 'The keyboard setting could not be changed.');
                return;
            }
            if (enabled) {
                Main.panel.statusArea.quickSettings.menu.close();
                // Let focus return to the application before opening the keyboard.
                this._showSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 350, () => {
                    this._showSource = 0;
                    if (this._settings.get_boolean(KEY))
                        Main.keyboard.open(Main.layoutManager.primaryIndex);
                    return GLib.SOURCE_REMOVE;
                });
            } else {
                Main.keyboard.close();
            }
        });
        this._indicator.quickSettingsItems.push(this._toggle);
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
        this._sync();
    }

    _sync() {
        const enabled = this._settings.get_boolean(KEY);
        this._toggle.checked = enabled;
        this._toggle.subtitle = enabled ? 'On' : 'Automatic';
    }

    disable() {
        if (this._showSource)
            GLib.Source.remove(this._showSource);
        this._showSource = 0;
        this._settings?.disconnect(this._changed);
        this._toggle?.destroy();
        this._indicator?.destroy();
        this._settings = null;
        this._toggle = null;
        this._indicator = null;
    }
}
