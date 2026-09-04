import Clutter from 'gi://Clutter';
import Meta from 'gi://Meta';
import St from 'gi://St';
import Graphene from 'gi://Graphene';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import {Keyboard} from 'resource:///org/gnome/shell/ui/keyboard.js';
import {Ripples} from 'resource:///org/gnome/shell/ui/ripples.js';
import {SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

export default class AdaptiveTouch extends Extension {
    enable() {
        this._touch = false;
        this._tracker = Meta.CursorTracker.get_for_display(global.display);
        this._indicator = new SystemIndicator();
        this._icon = this._indicator._addIndicator();
        this._icon.icon_name = 'input-tablet-symbolic';
        this._icon.accessible_name = 'Touch controls active';
        this._icon.visible = false;
        Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
        this._menuActor = Main.panel.statusArea.quickSettings.menu.actor;
        this._ripples = new Ripples(0.5, 0.5, 'adaptive-touch-ripple');
        this._ripples.addTo(Main.uiGroup);
        this._grip = new St.Button({
            style_class: 'adaptive-window-grip',
            accessible_name: 'Drag to move this window',
            reactive: true, can_focus: false, visible: false,
            child: new St.Widget({style_class: 'adaptive-window-grip-line',
                x_align: Clutter.ActorAlign.CENTER, y_align: Clutter.ActorAlign.CENTER}),
        });
        this._gripWrapper = new St.Widget({layout_manager: new Clutter.BinLayout()});
        this._gripWrapper.add_child(this._grip);
        Main.layoutManager.addChrome(this._gripWrapper, {trackFullscreen: true});
        this._grip.connect('touch-event', (_actor, event) => {
            if (event.type() === Clutter.EventType.TOUCH_BEGIN)
                return this._moveWindow(event);
            return Clutter.EVENT_PROPAGATE;
        });
        this._grip.connect('button-press-event', (_actor, event) => {
            if (event.get_button() === Clutter.BUTTON_PRIMARY)
                return this._moveWindow(event);
            return Clutter.EVENT_PROPAGATE;
        });
        global.display.connectObject('notify::focus-window', () => this._watchWindow(), this);
        Main.overview.connectObject('showing', () => this._syncGrip(),
            'hidden', () => this._syncGrip(), this);
        Main.layoutManager.connectObject('monitors-changed', () => this._syncGrip(), this);
        this._watchWindow();

        // GNOME 46 normally also requires the firmware tablet switch. This
        // model exposes touch correctly but does not reliably report that switch.
        // Keep the native keyboard and its normal explicit accessibility setting.
        this._injections = new InjectionManager();
        const extension = this;
        this._injections.overrideMethod(Main.keyboard, '_syncEnabled', original => {
            return function () {
                if (!extension._touch) {
                    original.call(this);
                    return;
                }
                if (!this._keyboard) {
                    this._keyboard = new Keyboard();
                    this._keyboard.connect('visibility-changed', () => {
                        this.emit('visibility-changed');
                        this._bottomDragAction.enabled = !this._keyboard.visible;
                    });
                }
            };
        });

        this._deviceSignal = global.backend.connect('last-device-changed', (_backend, device) => {
            const type = device.get_device_type();
            if (type === Clutter.InputDeviceType.TOUCHSCREEN_DEVICE)
                this._setTouch(true);
            else if ([Clutter.InputDeviceType.POINTER_DEVICE,
                Clutter.InputDeviceType.TOUCHPAD_DEVICE,
                Clutter.InputDeviceType.KEYBOARD_DEVICE].includes(type))
                this._setTouch(false);
        });
        this._eventSignal = global.stage.connect('captured-event', (_stage, event) => {
            if (event.type() === Clutter.EventType.TOUCH_BEGIN) {
                this._setTouch(true);
                const [x, y] = event.get_coords();
                this._ripples.playAnimation(x, y);
            }
            // Never consume touch events: apps and GNOME retain their gestures.
            return Clutter.EVENT_PROPAGATE;
        });
        this._cursorSignal = this._tracker.connect('visibility-changed', () => {
            if (this._touch && this._tracker.get_pointer_visible())
                this._tracker.set_pointer_visible(false);
        });
        this._setTouch(Main.keyboard._lastDeviceIsTouchscreen());
    }

    _setTouch(touch) {
        if (this._touch === touch)
            return;
        this._touch = touch;
        this._icon.visible = touch;
        if (touch)
            this._menuActor.add_style_class_name('adaptive-touch-controls');
        else
            this._menuActor.remove_style_class_name('adaptive-touch-controls');
        Main.keyboard._syncEnabled();
        this._tracker.set_pointer_visible(!touch);
        this._syncGrip();
    }

    _watchWindow() {
        this._window?.disconnectObject(this);
        this._window = global.display.focus_window;
        this._window?.connectObject('position-changed', () => this._syncGrip(),
            'size-changed', () => this._syncGrip(),
            'notify::fullscreen', () => this._syncGrip(),
            'unmanaged', () => { this._window = null; this._syncGrip(); }, this);
        this._syncGrip();
    }

    _syncGrip() {
        const window = this._window;
        const visible = this._touch && window && window.allows_move() &&
            !window.is_fullscreen() && !window.minimized &&
            !Main.overview.visible && !Main.sessionMode.isLocked &&
            window.get_window_type() === Meta.WindowType.NORMAL;
        this._grip.visible = !!visible;
        if (!visible) {
            this._gripWrapper.set_size(0, 0);
            return;
        }
        const rect = window.get_frame_rect();
        const scale = St.ThemeContext.get_for_stage(global.stage).scale_factor;
        const width = Math.min(110 * scale, rect.width / 3);
        this._grip.set_size(width, 26 * scale);
        this._gripWrapper.set_size(width, 26 * scale);
        this._gripWrapper.set_position(Math.round(rect.x + (rect.width - width) / 2), rect.y);
    }

    _moveWindow(event) {
        if (!this._window || Main.modalCount > 0)
            return Clutter.EVENT_PROPAGATE;
        const [x, y] = event.get_coords();
        return this._window.begin_grab_op(Meta.GrabOp.MOVING,
            event.get_device(), event.get_event_sequence(), event.get_time(),
            new Graphene.Point({x, y})) ? Clutter.EVENT_STOP : Clutter.EVENT_PROPAGATE;
    }

    disable() {
        global.display.disconnectObject(this);
        Main.overview.disconnectObject(this);
        Main.layoutManager.disconnectObject(this);
        this._window?.disconnectObject(this);
        this._window = null;
        if (this._grip) {
            Main.layoutManager.removeChrome(this._gripWrapper);
            this._gripWrapper.destroy();
            this._gripWrapper = null;
            this._grip = null;
        }
        if (this._deviceSignal)
            global.backend.disconnect(this._deviceSignal);
        if (this._eventSignal)
            global.stage.disconnect(this._eventSignal);
        if (this._cursorSignal)
            this._tracker.disconnect(this._cursorSignal);
        this._injections?.clear();
        this._menuActor?.remove_style_class_name('adaptive-touch-controls');
        this._ripples?.destroy();
        this._indicator?.destroy();
        this._touch = false;
        this._tracker?.set_pointer_visible(true);
        Main.keyboard._syncEnabled();
        this._tracker = null;
        this._indicator = null;
        this._injections = null;
        this._ripples = null;
    }
}
