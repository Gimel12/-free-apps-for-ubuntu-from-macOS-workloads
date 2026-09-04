"""Run on Xvfb to exercise GTK without touching the user's desktop."""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from library import Library
from app import MainWindow
from picker import Picker
from ui import Gtk,Gdk,style


with tempfile.TemporaryDirectory() as temp:
    lib=Library(temp)
    key=lib.save(dict(name='Thanks — Questions welcome',text='Thanks and if any questions, please let me know.',abbreviation=';thanks',favorite=True))
    style()
    with patch('app.integration.sync'):
        win=MainWindow(library=lib)
        while Gtk.events_pending():Gtk.main_iteration()
        assert win.current['id']==key
        win.name.set_text('Thanks — Happy to help')
        assert win.dirty
        assert win.save()
        assert lib.get(key)['name']=='Thanks — Happy to help'
        win.duplicate()
        assert win.current.get('id') is None
        win.abbr.set_text(';help')
        assert win.save()
        assert len(lib.all())==2
        win.delete()
        assert len(lib.all())==1
        win.filter=('favorites',None)
        win.new()
        win.name.set_text('Not a favorite')
        win.text.get_buffer().set_text('A new response')
        assert win.save()
        # Exercise save when the snippet is not present in the current filter.
        assert win.current['name']=='Not a favorite'
        win.filter=('all',None);win.refresh_nav();win.refresh_list(key)
        win.load(lib.get(key))
        with patch('app.Gtk.Dialog.run',return_value=Gtk.ResponseType.OK),patch('app.message'):
            win.preview_import([dict(name='Imported',text='Two\nlines',abbreviation=';imported',group_name='Support',enabled=True,note='')])
        assert any(s['name']=='Imported' for s in lib.all())
        win.refresh_list(key)
        assert win.listbox.get_selected_row().item['id']==key
        for _ in range(20):
            while Gtk.events_pending():Gtk.main_iteration()
        dest=Path(os.environ.get('BIZON_TEST_SCREENSHOT','/tmp/bizon-snippets-ui.png'))
        image=Gdk.pixbuf_get_from_window(win.get_window(),0,0,win.get_allocated_width(),win.get_allocated_height())
        image.savev(str(dest),'png',[],[])
        win.destroy()
        picker=Picker(library=lib)
        while Gtk.events_pending():Gtk.main_iteration()
        picker.search.set_text(';thanks');picker.refresh()
        assert picker.rows.get_row_at_index(0).item['id']==key
        picker.key(picker,type('Event',(),{'keyval':Gdk.KEY_Down})())
        picker.destroy()
        print('GTK editor, save, duplicate, trash, filtered save, picker search, keyboard navigation: passed')
