#!/usr/bin/python3
"""Z13 Fan Control — a native GTK desktop curve editor."""
import copy
import json
import math
from pathlib import Path
import uuid

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gdk, Gio, GLib, Gtk
import cairo
from curves import defaults, validate_profile, interpolate

HERE = Path(__file__).resolve().parent
CONFIG = Path(GLib.get_user_config_dir()) / 'z13-fan-control'
NAME = 'com.bizon.FanControl'


def label(text, css=None, **kwargs):
    widget = Gtk.Label(label=text, xalign=0, **kwargs)
    if css:
        widget.add_css_class(css)
    return widget


def button(text, callback, css=None):
    widget = Gtk.Button(label=text)
    if css:
        widget.add_css_class(css)
    widget.connect('clicked', callback)
    return widget


class CurveGraph(Gtk.DrawingArea):
    def __init__(self, owner):
        super().__init__(content_height=205, hexpand=True)
        self.owner = owner
        self.selected = None
        self.add_css_class('curve-graph')
        self.set_draw_func(self.draw)
        drag = Gtk.GestureDrag.new()
        drag.connect('drag-begin', self.begin)
        drag.connect('drag-update', self.move)
        self.add_controller(drag)

    def xy(self, point):
        t, p = point
        return 46 + (t - 30) / 65 * (self.get_width() - 70), 18 + (100 - p) / 100 * (self.get_height() - 52)

    def draw(self, area, cr, width, height):
        def text(x, y, value, size=11, alpha=0.65):
            cr.set_source_rgba(0.13, 0.28, 0.48, alpha)
            cr.select_font_face('Sans')
            cr.set_font_size(size)
            cr.move_to(x, y)
            cr.show_text(value)
        for speed in [0, 25, 50, 75, 100]:
            _, y = self.xy((30, speed))
            cr.set_source_rgb(0.9, 0.94, 0.99)
            cr.set_line_width(1)
            cr.move_to(46, y); cr.line_to(width - 24, y); cr.stroke()
            text(5, y + 4, f'{speed}%')
        for temp in [30, 45, 60, 75, 85, 95]:
            x, _ = self.xy((temp, 0))
            text(x - 11, height - 9, f'{temp}°')
        current = self.owner.draft[self.owner.fan]
        other = self.owner.draft['gpu' if self.owner.fan == 'cpu' else 'cpu']
        x, bottom = self.xy((30, 0))
        cr.move_to(x, bottom)
        for point in current:
            cr.line_to(*self.xy(point))
        cr.line_to(self.xy((95, 0))[0], bottom); cr.close_path()
        gradient = cairo.LinearGradient(0, 18, 0, bottom)
        gradient.add_color_stop_rgba(0, 0.14, 0.48, 1, 0.22)
        gradient.add_color_stop_rgba(1, 0.14, 0.48, 1, 0.025)
        cr.set_source(gradient); cr.fill()
        for points, faint in [(other, True), (current, False)]:
            cr.set_source_rgba(0.08, 0.40, 0.94, 0.24 if faint else 1)
            cr.set_line_width(2 if faint else 3)
            cr.set_dash([5, 5] if faint else [])
            for i, point in enumerate(points):
                (cr.move_to if i == 0 else cr.line_to)(*self.xy(point))
            cr.stroke()
        cr.set_dash([])
        reading = self.owner.status.get('temperature' if self.owner.fan == 'cpu' else 'gpu_temperature')
        if reading is not None:
            x, _ = self.xy((min(95, max(30, reading)), 0))
            cr.set_source_rgba(0.1, 0.3, 0.7, 0.35)
            cr.set_line_width(1); cr.set_dash([3, 4])
            cr.move_to(x, 18); cr.line_to(x, bottom); cr.stroke(); cr.set_dash([])
            text(min(x + 6, width - 94), 33, f'Live {reading:.0f}°C', 11, 0.85)
        for i, point in enumerate(current):
            x, y = self.xy(point)
            cr.new_path()
            cr.set_source_rgb(1, 1, 1); cr.arc(x, y, 6, 0, math.tau); cr.fill_preserve()
            cr.set_source_rgb(0.08, 0.40, 0.94); cr.set_line_width(2.5); cr.stroke()

    def begin(self, gesture, x, y):
        points = self.owner.draft[self.owner.fan]
        self.selected = min(range(8), key=lambda i: math.dist(self.xy(points[i]), (x, y)))
        if math.dist(self.xy(points[self.selected]), (x, y)) > 32:
            self.selected = None
            return
        self.origin = self.xy(points[self.selected])

    def move(self, gesture, dx, dy):
        if self.selected is None or self.selected == 7:
            return
        points, i = self.owner.draft[self.owner.fan], self.selected
        x, y = self.origin[0] + dx, self.origin[1] + dy
        temp = round(30 + (x - 46) / (self.get_width() - 70) * 65)
        temp = 30 if i == 0 else max(points[i-1][0] + 2, min(points[i+1][0] - 2, temp))
        speed = round(100 - (y - 18) / (self.get_height() - 52) * 100)
        speed = max(points[i-1][1] if i else 0, min(points[i+1][1], speed))
        points[i] = [temp, speed]
        self.owner.update_fields()
        self.owner.changed()


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title='Z13 Fan Control', default_width=1040, default_height=810)
        self.set_size_request(760, 540)
        self.status, self.busy, self.polling, self.dirty = {}, False, False, False
        self.profiles = self.load_profiles()
        self.selected = 'quiet' if 'quiet' in self.profiles else next(iter(self.profiles))
        self.draft = copy.deepcopy(self.profiles[self.selected])
        self.fan = 'cpu'
        self.syncing = False
        self.cancel = Gio.Cancellable()
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.overlay = Adw.ToastOverlay()
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.overlay.set_child(root); self.set_content(self.overlay)
        header = Gtk.HeaderBar()
        branding = Gtk.Box(spacing=10)
        branding.append(Gtk.Image.new_from_file(str(HERE / 'icon.svg')))
        branding.append(label('Z13 Fan Control', 'brand'))
        header.set_title_widget(branding)
        auto = button('Automatic cooling', self.automatic)
        auto.set_tooltip_text('Restore firmware-controlled fans and release low-power limits')
        header.pack_end(auto); root.append(header)

        body = Gtk.Box(hexpand=True, vexpand=True)
        root.append(body)
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, width_request=182)
        sidebar.add_css_class('sidebar')
        sidebar.append(label('YOUR PROFILES', 'eyebrow'))
        self.profile_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        self.profile_list.add_css_class('profiles')
        self.profile_list.connect('row-selected', self.select_profile)
        sidebar.append(self.profile_list)
        sidebar.append(button('+  New profile', self.new_profile, 'flat'))
        spacer = Gtk.Box(vexpand=True); sidebar.append(spacer)
        sidebar.append(button('Duplicate', self.duplicate, 'flat'))
        sidebar.append(button('Delete profile', self.delete_profile, 'flat'))
        sidebar.append(label('ASUS ROG FLOW Z13', 'eyebrow'))
        sidebar.append(label('Local control\nNo account needed', 'muted'))
        body.append(sidebar)

        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True, vexpand=True)
        right = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
        body.append(right); right.append(scroller)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        content.add_css_class('content'); scroller.set_child(content)
        heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        heading.append(label('Cooling overview', 'page-title'))
        self.active = label('Connecting to your Z13…', 'muted', wrap=True)
        heading.append(self.active); content.append(heading)
        stats = Gtk.Box(spacing=10, homogeneous=True)
        self.stats = {}
        for key, title in [('temperature', 'CPU TEMP'), ('gpu_temperature', 'GPU TEMP'),
                           ('cpu_rpm', 'CPU FAN · RPM'), ('gpu_rpm', 'GPU FAN · RPM')]:
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.add_css_class('stat-card'); card.append(label(title, 'eyebrow'))
            value = label('—', 'stat-value'); card.append(value)
            self.stats[key] = value; stats.append(card)
        content.append(stats)

        editor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        editor.add_css_class('editor'); content.append(editor)
        name_row = Gtk.Box(spacing=8)
        self.name_entry = Gtk.Entry(hexpand=True, max_length=48)
        self.name_entry.add_css_class('profile-name'); self.name_entry.set_placeholder_text('Profile name')
        self.name_entry.connect('changed', self.name_changed)
        name_row.append(self.name_entry)
        self.cpu_button = Gtk.ToggleButton(label='CPU')
        self.gpu_button = Gtk.ToggleButton(label='GPU'); self.gpu_button.set_group(self.cpu_button)
        tabs = Gtk.Box(); tabs.add_css_class('linked')
        tabs.append(self.cpu_button); tabs.append(self.gpu_button); name_row.append(tabs)
        self.cpu_button.connect('toggled', lambda b: self.select_fan('cpu') if b.get_active() else None)
        self.gpu_button.connect('toggled', lambda b: self.select_fan('gpu') if b.get_active() else None)
        self.cpu_button.set_active(True); editor.append(name_row)
        editor.append(label('Drag the blue points, or enter exact values below.', 'muted', wrap=True))
        self.graph = CurveGraph(self); editor.append(self.graph)
        grid = Gtk.Grid(column_spacing=5, row_spacing=5, column_homogeneous=True)
        self.fields = []
        for i in range(8):
            grid.attach(label(f'{i + 1}', 'point-number', halign=Gtk.Align.CENTER), i, 0, 1, 1)
            t = Gtk.SpinButton.new_with_range(30, 95, 1)
            p = Gtk.SpinButton.new_with_range(0, 100, 1)
            for widget in [t, p]:
                widget.set_numeric(True); widget.set_width_chars(2)
                widget.add_css_class('point-input')
            t.set_tooltip_text(f'Point {i+1} temperature in °C')
            p.set_tooltip_text(f'Point {i+1} fan duty in percent')
            t.set_sensitive(i not in (0, 7)); p.set_sensitive(i != 7)
            t.connect('value-changed', self.point_changed, i, 0)
            p.connect('value-changed', self.point_changed, i, 1)
            grid.attach(t, i, 1, 1, 1); grid.attach(p, i, 2, 1, 1)
            self.fields.append((t, p))
        exact = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        exact.append(grid)
        legend = Gtk.Box(spacing=8)
        legend.append(label('Top: °C   /   Bottom: fan %', 'muted', hexpand=True))
        legend.append(button('Copy to other fan', self.copy_curve, 'flat')); exact.append(legend)
        expander = Gtk.Expander(label='Exact temperature & fan values')
        expander.set_child(exact); editor.append(expander)
        editor.append(label('Full cooling at 95°C. The faint curve shows the other fan.', 'muted', wrap=True))
        lowrow = Gtk.Box(spacing=12)
        lowtext = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
        lowtext.append(label('Low power for light tasks', 'row-title'))
        lowtext.append(label('Less CPU power for reading and browsing.', 'muted', wrap=True))
        lowrow.append(lowtext)
        self.low_power = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.low_power.connect('notify::active', self.low_changed)
        lowrow.append(self.low_power); content.append(lowrow)
        self.feedback = label('Changes affect the fans only when you apply.', 'muted', wrap=True)
        content.append(self.feedback)
        footer = Gtk.Box(spacing=10)
        footer.add_css_class('action-bar')
        self.save_button = button('Save profile', self.save)
        self.apply_button = button('Apply profile', self.apply_profile, 'suggested-action')
        self.apply_button.set_hexpand(True)
        footer.append(self.save_button); footer.append(self.apply_button); right.append(footer)
        self.rebuild_list(); self.show_draft()
        self.connect('close-request', self.close_request)
        self.timer = GLib.timeout_add_seconds(2, self.poll)
        self.poll()

    def load_profiles(self):
        CONFIG.mkdir(parents=True, exist_ok=True)
        path = CONFIG / 'profiles.json'
        if path.exists():
            try:
                raw = json.loads(path.read_text())
                profiles = [validate_profile(p) for p in raw['profiles']]
                if profiles:
                    return {p['id']: p for p in profiles}
            except (ValueError, TypeError, KeyError):
                path.replace(CONFIG / f'profiles-recovered-{GLib.get_real_time()}.json')
        return {p['id']: p for p in defaults()}

    def persist(self):
        path = CONFIG / 'profiles.json'
        data = json.dumps({'version': 1, 'profiles': list(self.profiles.values())}, indent=2)
        temp = path.with_suffix('.tmp'); temp.write_text(data); temp.replace(path)

    def rebuild_list(self):
        self.rebuilding = True
        child = self.profile_list.get_first_child()
        while child:
            self.profile_list.remove(child); child = self.profile_list.get_first_child()
        for profile in self.profiles.values():
            row = Gtk.ListBoxRow(); row.identifier = profile['id']
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
            box.append(label(profile['name'], 'profile-label', wrap=True))
            box.append(label('Low power' if profile['low_power'] else 'Custom curve', 'profile-detail'))
            row.set_child(box); self.profile_list.append(row)
            if row.identifier == self.selected:
                self.profile_list.select_row(row)
        self.rebuilding = False

    def select_profile(self, box, row):
        if getattr(self, 'rebuilding', False) or row is None or row.identifier == self.selected:
            return
        destination = row.identifier
        if self.dirty:
            self.confirm('Save your changes?', 'Save this curve before opening another profile.',
                         lambda: self.switch_to(destination), save=True)
        else:
            self.switch_to(destination)

    def switch_to(self, identifier):
        self.selected = identifier; self.draft = copy.deepcopy(self.profiles[identifier])
        self.dirty = False; self.rebuild_list(); self.show_draft()

    def show_draft(self):
        self.syncing = True
        self.name_entry.set_text(self.draft['name']); self.low_power.set_active(self.draft['low_power'])
        self.syncing = False
        self.update_fields(); self.changed(mark=False)

    def update_fields(self):
        if not hasattr(self, 'fields'):
            return
        self.syncing = True
        for i, (t, p) in enumerate(self.fields):
            t.set_value(self.draft[self.fan][i][0]); p.set_value(self.draft[self.fan][i][1])
        self.syncing = False
        self.graph.queue_draw()

    def select_fan(self, fan):
        self.fan = fan; self.update_fields()

    def name_changed(self, entry):
        if not self.syncing:
            self.draft['name'] = entry.get_text(); self.changed()

    def low_changed(self, switch, _):
        if not self.syncing:
            self.draft['low_power'] = switch.get_active(); self.changed()

    def point_changed(self, widget, index, part):
        if not self.syncing:
            self.draft[self.fan][index][part] = widget.get_value_as_int(); self.changed()

    def changed(self, mark=True):
        if not hasattr(self, 'feedback'):
            return
        if mark:
            self.dirty = True
        try:
            validate_profile(self.draft)
            self.valid = True
            self.feedback.set_text('Unsaved changes · Apply also saves your profile.' if self.dirty else
                                   'Saved locally · Apply to use this curve on your fans.')
        except ValueError as error:
            self.valid = False; self.feedback.set_text(str(error))
        self.save_button.set_sensitive(self.valid and not self.busy)
        self.apply_button.set_sensitive(self.valid and not self.busy and bool(self.status))
        self.graph.queue_draw()

    def save(self, *_):
        try:
            self.draft = validate_profile(self.draft)
            self.profiles[self.selected] = copy.deepcopy(self.draft)
            self.persist(); self.dirty = False; self.rebuild_list(); self.changed(mark=False)
            return True
        except (ValueError, OSError) as error:
            self.toast(str(error)); return False

    def copy_curve(self, *_):
        other = 'gpu' if self.fan == 'cpu' else 'cpu'
        self.draft[other] = copy.deepcopy(self.draft[self.fan]); self.changed()
        self.toast(f'Copied to {other.upper()} curve')

    def make_profile(self, duplicate=False):
        if self.dirty and not self.save():
            return
        profile = copy.deepcopy(self.draft if duplicate else defaults()[1])
        profile['id'] = uuid.uuid4().hex
        profile['name'] = (profile['name'][:39] + ' copy') if duplicate else 'My profile'
        self.profiles[profile['id']] = profile
        self.persist(); self.switch_to(profile['id']); self.name_entry.grab_focus()
        self.name_entry.select_region(0, -1)

    def new_profile(self, *_): self.make_profile()
    def duplicate(self, *_): self.make_profile(True)

    def delete_profile(self, *_):
        if len(self.profiles) == 1 or self.selected == 'quiet':
            self.toast('Keep Quiet reading and at least one profile. Duplicate it to experiment.'); return
        def remove():
            del self.profiles[self.selected]
            self.persist(); self.switch_to(next(iter(self.profiles)))
        self.confirm('Delete this profile?', 'The currently applied fan curve will stay active.', remove)

    def confirm(self, title, body, callback, save=False):
        dialog = Adw.MessageDialog(transient_for=self, heading=title, body=body)
        dialog.add_response('cancel', 'Cancel')
        if save:
            dialog.add_response('discard', 'Discard changes')
        dialog.add_response('accept', 'Save' if save else 'Delete')
        dialog.set_default_response('cancel'); dialog.set_close_response('cancel')
        def response(_, value):
            if value == 'discard' or (value == 'accept' and (not save or self.save())):
                self.dirty = False; callback()
            elif value == 'cancel':
                self.rebuild_list()
        dialog.connect('response', response); dialog.present()

    def call(self, method, callback, parameter=None):
        args = GLib.Variant('(s)', (json.dumps(parameter),)) if parameter is not None else None
        def complete(bus, result):
            try:
                value = bus.call_finish(result)
                callback(value.unpack() if value else (), None)
            except GLib.Error as error:
                callback(None, error)
        self.bus.call(NAME, '/com/bizon/FanControl', NAME, method, args, None,
            Gio.DBusCallFlags.NONE, 15000, self.cancel, complete)

    def apply_profile(self, *_):
        if self.busy or not self.save():
            return
        self.busy = True; self.changed(mark=False); self.apply_button.set_label('Applying…')
        data = copy.deepcopy(self.draft)
        def apply_now():
            self.call('SetProfile', self.applied, data)
        if data['low_power'] and (Path(GLib.get_user_config_dir()) / 'systemd/user/bizon-game-mode.service').exists():
            process = Gio.Subprocess.new(['/usr/bin/systemctl', '--user', 'stop', 'bizon-game-mode.service'],
                                         Gio.SubprocessFlags.STDERR_PIPE)
            def stopped(source, result):
                try:
                    source.wait_check_finish(result); apply_now()
                except GLib.Error as error:
                    self.applied(None, error)
            process.wait_check_async(self.cancel, stopped)
        else:
            apply_now()

    def applied(self, result, error):
        self.busy = False; self.apply_button.set_label('Apply profile')
        if error:
            self.toast('Could not apply: ' + error.message)
        else:
            self.toast('Profile applied · Stays active when you close the app')
        self.changed(mark=False); self.poll()

    def automatic(self, *_):
        if self.busy: return
        self.busy = True; self.changed(mark=False)
        def done(result, error):
            self.busy = False
            self.toast(error.message if error else 'Automatic cooling restored')
            self.changed(mark=False); self.poll()
        self.call('Automatic', done)

    def poll(self):
        if self.polling or self.busy or self.cancel.is_cancelled():
            return GLib.SOURCE_CONTINUE
        self.polling = True
        def complete(result, error):
            self.polling = False
            if self.cancel.is_cancelled(): return
            if error:
                self.status = {}; self.active.set_text('Cooling service unavailable · Your saved profiles are still here.')
                for widget in self.stats.values(): widget.set_text('—')
            else:
                self.status = json.loads(result[0])
                profile = self.status.get('profile')
                mode = self.status['mode']
                active = profile['name'] if profile else {'automatic': 'Automatic cooling', 'quiet': 'Quiet Mode',
                    'manual': f"Manual · {self.status['speed']}%"}.get(mode, 'Custom curve')
                power = self.status.get('power')
                self.active.set_text(f'Active: {active}' + (f'   ·   Chip power {power:.1f} W' if power is not None else ''))
                for key in ('temperature', 'gpu_temperature'):
                    value = self.status.get(key)
                    self.stats[key].set_text(f'{value:.0f}°C' if value is not None else '—')
                for i, key in enumerate(('cpu_rpm', 'gpu_rpm')):
                    value = self.status['rpm'][i]
                    self.stats[key].set_text(f'{value:,}' if value is not None else '—')
            self.changed(mark=False)
        self.call('Status', complete)
        return GLib.SOURCE_CONTINUE

    def toast(self, message):
        self.overlay.add_toast(Adw.Toast(title=message, timeout=3))

    def close_request(self, *_):
        if self.dirty:
            self.confirm('Save your changes?', 'Keep your edited profile for next time.', self.close, save=True)
            return True
        self.cancel.cancel()
        GLib.source_remove(self.timer)
        return False


class Application(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.bizon.Z13FanControl', flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        self.get_style_manager().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        provider = Gtk.CssProvider(); provider.load_from_path(str(HERE / 'style.css'))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        window = self.get_active_window() or Window(self)
        window.present()


if __name__ == '__main__':
    Application().run(None)
