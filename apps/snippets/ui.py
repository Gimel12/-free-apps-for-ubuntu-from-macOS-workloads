import datetime
import re
from pathlib import Path
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
from gi.repository import Gdk, Gtk, Pango, GLib
GLib.set_prgname('bizon-snippets')
Gdk.set_program_class('BizonSnippets')


def style():
    provider = Gtk.CssProvider()
    provider.load_from_path(str(Path(__file__).with_name('style.css')))
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


def css(widget, name):
    widget.get_style_context().add_class(name)
    return widget


def label(text, cls=None):
    widget = Gtk.Label(label=text, xalign=0)
    if cls:
        css(widget, cls)
    return widget


def button(text, callback, cls=None):
    widget = Gtk.Button(label=text)
    widget.connect('clicked', callback)
    if cls:
        css(widget, cls)
    return widget


def message(parent, title, detail):
    dialog = Gtk.MessageDialog(transient_for=parent, modal=True, message_type=Gtk.MessageType.INFO,
                               buttons=Gtk.ButtonsType.OK, text=title)
    dialog.format_secondary_text(detail)
    dialog.run()
    dialog.destroy()


TOKEN = re.compile(r'\{\{\s*([^{}]+?)\s*\}\}')


def render(text, parent=None):
    names = list(dict.fromkeys(TOKEN.findall(text)))
    if not names:
        return text
    now = datetime.datetime.now()
    values = {'date':now.strftime('%Y-%m-%d'), 'time':now.strftime('%H:%M'),
              'clipboard':Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_text() or ''}
    fields = [n for n in names if n not in values]
    if fields:
        dialog = Gtk.Dialog(title='Fill in your snippet', transient_for=parent, modal=True)
        dialog.set_default_size(460, 180)
        dialog.set_position(Gtk.WindowPosition.CENTER)
        dialog.set_keep_above(True)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Use snippet',Gtk.ResponseType.OK)
        dialog.set_default_response(Gtk.ResponseType.OK)
        content = dialog.get_content_area()
        content.set_border_width(22)
        content.set_spacing(10)
        entries = {}
        for field in fields:
            content.pack_start(label(field,'muted'),False,False,0)
            entry = Gtk.Entry(activates_default=True)
            entries[field] = entry
            content.pack_start(entry,False,False,0)
        dialog.show_all()
        next(iter(entries.values())).grab_focus()
        response = dialog.run()
        values.update({n:e.get_text() for n,e in entries.items()})
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return None
    return TOKEN.sub(lambda m:values[m.group(1).strip()],text)
