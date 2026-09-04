#!/usr/bin/python3
import json
import os
import sys
import subprocess
from pathlib import Path
from library import Library, matches
from ui import Gtk, Gdk, Pango, style, css, label, button, render, message


class Picker(Gtk.Window):
    def __init__(self, library=None):
        super().__init__(title='Snippets — Quick paste')
        self.lib=library or Library()
        self.items=self.lib.all()
        self.set_default_size(660,480)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_keep_above(True)
        self.connect('destroy',lambda *_:Gtk.main_quit() if Gtk.main_level() else None)
        self.connect('key-press-event',self.key)
        header=Gtk.HeaderBar(title='Quick paste',subtitle='Your words, one shortcut away',show_close_button=True)
        header.pack_end(button('Open library',self.open_library,'flat'))
        self.set_titlebar(header)
        box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14,margin=18)
        self.add(box)
        self.search=Gtk.SearchEntry(placeholder_text='Search by name, abbreviation or content…')
        self.search.connect('search-changed',lambda *_:self.refresh())
        self.search.connect('activate',lambda *_:self.choose())
        box.pack_start(self.search,False,False,0)
        self.rows=css(Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE),'snippet-list')
        self.rows.connect('row-activated',lambda *_:self.choose())
        scroll=Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.rows);box.pack_start(scroll,True,True,0)
        self.empty=label('No matching snippets. Add one in your library.','muted')
        self.empty.set_no_show_all(True);box.pack_start(self.empty,False,False,0)
        box.pack_start(label('↑ ↓  Select     Enter  Paste     Esc  Cancel','status'),False,False,0)
        self.refresh();self.show_all();self.search.grab_focus();self.present()

    def refresh(self):
        for row in self.rows.get_children():self.rows.remove(row)
        for item in self.items:
            if not matches(item,self.search.get_text()):continue
            row=Gtk.ListBoxRow();row.item=item
            box=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,margin=14)
            top=Gtk.Box(spacing=10)
            title=label(('★  ' if item['favorite'] else '')+item['name'],'snippet-name')
            title.set_ellipsize(Pango.EllipsizeMode.END)
            top.pack_start(title,True,True,0)
            top.pack_end(label(item['abbreviation'] or item['group_name'],'tag'),False,False,0)
            box.pack_start(top,False,False,0)
            preview=label(' '.join(item['text'].split()),'preview')
            preview.set_ellipsize(Pango.EllipsizeMode.END);preview.set_max_width_chars(70)
            box.pack_start(preview,False,False,0)
            row.add(box);self.rows.add(row)
        self.rows.show_all()
        first=self.rows.get_row_at_index(0)
        self.empty.set_visible(first is None)
        if first:self.rows.select_row(first)

    def choose(self):
        row=self.rows.get_selected_row()
        if not row:return
        item=self.lib.get(row.item['id'])
        if not item or item['deleted']:return
        if item['note']:
            d=Gtk.MessageDialog(transient_for=self,modal=True,text='This snippet needs review',secondary_text=item['note'])
            d.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Paste as plain text',Gtk.ResponseType.OK)
            answer=d.run();d.destroy()
            if answer!=Gtk.ResponseType.OK:return
        value=render(item['text'],self)
        if value is not None:
            print(json.dumps({'text':value}),flush=True)
            self.destroy()

    def key(self,_w,event):
        if event.keyval==Gdk.KEY_Escape:
            self.destroy();return True
        if event.keyval in (Gdk.KEY_Down,Gdk.KEY_Up):
            row=self.rows.get_selected_row()
            index=(row.get_index() if row else 0)+(1 if event.keyval==Gdk.KEY_Down else -1)
            target=self.rows.get_row_at_index(max(0,index))
            if target:
                self.rows.select_row(target)
                allocation=target.get_allocation()
                adjustment=self.rows.get_parent().get_parent().get_vadjustment()
                if allocation.y<adjustment.get_value():adjustment.set_value(allocation.y)
                elif allocation.y+allocation.height>adjustment.get_value()+adjustment.get_page_size():
                    adjustment.set_value(allocation.y+allocation.height-adjustment.get_page_size())
            return True
        return False

    def open_library(self,*_):
        subprocess.Popen(['/usr/bin/python3',str(Path(__file__).with_name('app.py'))],start_new_session=True,
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.destroy()


if __name__=='__main__':
    os.umask(0o077)
    style()
    if len(sys.argv)>2 and sys.argv[1]=='--expand':
        lib=Library()
        item=lib.get(sys.argv[2])
        if item and item['enabled'] and not item['deleted'] and lib.setting('paused')!='yes':
            value=render(item['text'])
            if value is not None:print(json.dumps({'text':value}))
    else:
        Picker()
        Gtk.main()
