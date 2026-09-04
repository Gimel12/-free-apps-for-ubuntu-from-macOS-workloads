import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import Clutter from 'gi://Clutter';
import {Extension, InjectionManager} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class ClockTopLeft extends Extension {
    enable() {
        this._clock = Main.panel.statusArea.dateMenu.container;
        this._parent = this._clock.get_parent();
        this._index = this._parent.get_children().indexOf(this._clock);
        this._parent.remove_child(this._clock);
        const leftBox = Main.panel._leftBox;
        const activities = Main.panel.statusArea.activities.container;
        const activitiesIndex = leftBox.get_children().indexOf(activities);
        leftBox.insert_child_at_index(this._clock, activitiesIndex + 1);
        // The stock panel reserves half its width on each side of the clock.
        // With an empty center, allow the tray to use the space left by the date.
        this._injections = new InjectionManager();
        this._injections.overrideMethod(Object.getPrototypeOf(Main.panel), 'vfunc_allocate', original => function (box) {
            original.call(this, box);
            const [, centerWidth] = this._centerBox.get_preferred_width(-1);
            if (centerWidth > 0)
                return;
            const width = box.x2 - box.x1;
            const [, leftWidth] = this._leftBox.get_preferred_width(-1);
            const [, rightWidth] = this._rightBox.get_preferred_width(-1);
            const available = Math.max(0, width - leftWidth - 24);
            const trayWidth = Math.min(rightWidth, available);
            const rtl = this.get_text_direction() === Clutter.TextDirection.RTL;
            this._rightBox.allocate(new Clutter.ActorBox({
                x1: rtl ? 0 : width - trayWidth,
                x2: rtl ? trayWidth : width,
                y1: 0, y2: box.y2 - box.y1,
            }));
        });
        Main.panel.queue_relayout();
        this._syncCompact = () => {
            const monitor = Main.layoutManager.primaryMonitor;
            if (monitor && monitor.width < monitor.height)
                Main.panel.add_style_class_name('bizon-portrait-panel');
            else
                Main.panel.remove_style_class_name('bizon-portrait-panel');
        };
        Main.layoutManager.connectObject('monitors-changed', this._syncCompact, this);
        this._syncCompact();
    }

    disable() {
        Main.layoutManager.disconnectObject(this);
        Main.panel.remove_style_class_name('bizon-portrait-panel');
        this._injections?.clear();
        this._injections = null;
        if (this._clock && this._parent) {
            this._clock.get_parent()?.remove_child(this._clock);
            this._parent.insert_child_at_index(this._clock, this._index);
        }
        this._clock = null;
        this._parent = null;
        Main.panel.queue_relayout();
    }
}
