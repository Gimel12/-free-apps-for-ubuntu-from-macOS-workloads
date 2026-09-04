#!/usr/bin/python3
"""Snippets — a native personal text expansion workspace."""
import os
import sys
from pathlib import Path
from ui import Gtk, Gdk, Pango, style, css, label, button, message, render
from gi.repository import Gio, GLib
from library import Library, matches
from importers import parse_file
import integration


class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, app=None, library=None):
        super().__init__(application=app, title='Snippets')
        self.lib = library or Library()
        self.current = None
        self.filter = ('all',None)
        self.loading = False
        self.dirty = False
        self.set_default_size(1200, 760)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_icon_from_file(str(Path(__file__).with_name('icon.svg')))
        self.connect('delete-event',lambda *_:not self.guard())
        self.connect('key-press-event',self.keys)
        header = Gtk.HeaderBar(title='Snippets', subtitle='Your words, ready when you are', show_close_button=True)
        header.pack_start(label('  PERSONAL WORKSPACE','eyebrow'))
        header.pack_end(label('On this computer','pill'))
        self.set_titlebar(header)
        layout = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.add(layout)
        side = css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=20), 'sidebar')
        side.set_size_request(220,-1)
        inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14,margin=20)
        side.pack_start(inner,True,True,0)
        brand = Gtk.Box(spacing=10)
        brand.pack_start(label('S','brand-icon'),False,False,0)
        brand.pack_start(label('Snippets','brand'),False,False,0)
        inner.pack_start(brand,False,False,6)
        inner.pack_start(button('+  New snippet',lambda *_:self.new(),'primary'),False,False,6)
        inner.pack_start(label('LIBRARY','eyebrow'),False,False,0)
        self.nav = css(Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE),'nav')
        self.nav.connect('row-selected',self.navigate)
        nav_scroll=Gtk.ScrolledWindow()
        nav_scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        nav_scroll.add(self.nav)
        inner.pack_start(nav_scroll,True,True,0)
        inner.pack_start(button('+  New group',self.new_group,'flat'),False,False,0)
        inner.pack_start(Gtk.Separator(),False,False,0)
        inner.pack_start(button('Import snippets',self.import_dialog),False,False,0)
        inner.pack_start(button('Export library',self.export_dialog,'flat'),False,False,0)
        self.pause = Gtk.CheckButton(label='Pause typed expansion')
        self.pause.set_active(self.lib.setting('paused')=='yes')
        self.pause.connect('toggled',self.toggle_pause)
        inner.pack_start(self.pause,False,False,0)
        inner.pack_start(button('Quick guide',self.help_dialog,'flat'),False,False,0)
        inner.pack_start(label('Ctrl + .   Quick paste\nCtrl + N  New snippet','status'),False,False,0)
        layout.pack_start(side,False,False,0)
        middle=css(Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8),'list-pane')
        middle.set_size_request(310,-1)
        heading=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=12,margin=22)
        self.list_title=label('All snippets','section-title')
        self.count=label('','muted')
        heading.pack_start(self.list_title,False,False,0)
        heading.pack_start(self.count,False,False,0)
        self.search=Gtk.SearchEntry(placeholder_text='Search your snippets…')
        self.search.connect('search-changed',lambda *_:self.refresh_list())
        heading.pack_start(self.search,False,False,0)
        middle.pack_start(heading,False,False,0)
        self.listbox=css(Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE),'snippet-list')
        self.listbox.connect('row-selected',self.select)
        scroll=Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER,Gtk.PolicyType.AUTOMATIC)
        scroll.add(self.listbox)
        middle.pack_start(scroll,True,True,0)
        layout.pack_start(middle,False,False,0)
        self.stack=Gtk.Stack()
        layout.pack_start(self.stack,True,True,0)
        empty=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=14)
        empty.set_valign(Gtk.Align.CENTER)
        empty.set_halign(Gtk.Align.CENTER)
        empty.pack_start(label('A little less typing.','empty-title'),False,False,0)
        empty.pack_start(label('Select a snippet, or create your next go-to response.','empty-body'),False,False,0)
        empty.pack_start(button('Create a snippet',lambda *_:self.new(),'primary'),False,False,10)
        self.stack.add_named(empty,'empty')
        self.build_editor()
        self.refresh_nav()
        self.refresh_list()
        self.show_all()
        self.note.hide()
        self.stack.set_visible_child_name('empty')
        self.refresh_list()
        self.version=self.lib.db.execute('PRAGMA data_version').fetchone()[0]
        GLib.timeout_add_seconds(2,self.check_external)

    def build_editor(self):
        pane=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=18,margin=30)
        top=Gtk.Box(spacing=10)
        top.pack_start(label('SNIPPET EDITOR','eyebrow'),True,True,0)
        self.state=label('Saved','status')
        top.pack_end(self.state,False,False,0)
        pane.pack_start(top,False,False,0)
        self.name=css(Gtk.Entry(placeholder_text='Give this snippet a name'),'title-input')
        self.name.connect('changed',self.changed)
        pane.pack_start(self.name,False,False,0)
        fields=Gtk.Grid(column_spacing=18,row_spacing=7)
        fields.attach(label('ABBREVIATION','eyebrow'),0,0,1,1)
        fields.attach(label('GROUP','eyebrow'),1,0,1,1)
        self.abbr=css(Gtk.Entry(placeholder_text='e.g. ;thanks'),'abbreviation')
        self.abbr.set_hexpand(True)
        self.abbr.connect('changed',self.changed)
        fields.attach(self.abbr,0,1,1,1)
        self.group=Gtk.ComboBoxText()
        self.group.set_hexpand(True)
        self.group.connect('changed',self.changed)
        fields.attach(self.group,1,1,1,1)
        pane.pack_start(fields,False,False,0)
        options=Gtk.Box(spacing=16)
        self.enabled=Gtk.CheckButton(label='Expand abbreviation as I type')
        self.enabled.connect('toggled',self.changed)
        options.pack_start(self.enabled,True,True,0)
        self.favorite=Gtk.CheckButton(label='Favorite')
        self.favorite.connect('toggled',self.changed)
        options.pack_end(self.favorite,False,False,0)
        pane.pack_start(options,False,False,0)
        self.note=css(Gtk.Label(xalign=0),'warning')
        self.note.set_line_wrap(True)
        self.note.set_max_width_chars(60)
        self.note.set_no_show_all(True)
        pane.pack_start(self.note,False,False,0)
        pane.pack_start(label('CONTENT','eyebrow'),False,False,0)
        self.text=Gtk.TextView(wrap_mode=Gtk.WrapMode.WORD_CHAR)
        self.text.set_left_margin(20);self.text.set_right_margin(20)
        self.text.set_top_margin(18);self.text.set_bottom_margin(18)
        self.text.set_pixels_below_lines(7)
        self.text.get_buffer().connect('changed',self.changed)
        frame=css(Gtk.ScrolledWindow(),'editor-frame')
        frame.set_policy(Gtk.PolicyType.AUTOMATIC,Gtk.PolicyType.AUTOMATIC)
        frame.add(self.text)
        pane.pack_start(frame,True,True,0)
        tokens=Gtk.Box(spacing=6)
        tokens.pack_start(label('Insert','muted'),False,False,0)
        for name,value in [('Date','{{date}}'),('Time','{{time}}'),('Clipboard','{{clipboard}}'),('Fill-in','{{name}}')]:
            tokens.pack_start(button(name,lambda _,v=value:self.insert_token(v),'token'),False,False,0)
        pane.pack_start(tokens,False,False,0)
        self.length=label('','status')
        pane.pack_start(self.length,False,False,0)
        pane.pack_start(Gtk.Separator(),False,False,0)
        actions=Gtk.Box(spacing=8)
        self.delete_button=button('Move to trash',self.delete,'flat')
        css(self.delete_button,'danger')
        actions.pack_start(self.delete_button,False,False,0)
        self.duplicate_button=button('Duplicate',self.duplicate,'flat')
        actions.pack_start(self.duplicate_button,False,False,0)
        self.save_button=button('Save snippet',self.save,'primary')
        actions.pack_end(self.save_button,False,False,0)
        actions.pack_end(button('Copy',self.copy),False,False,0)
        pane.pack_start(actions,False,False,0)
        self.stack.add_named(pane,'editor')

    def changed(self,*_):
        if self.loading:
            return
        self.dirty=True
        self.state.set_text('Unsaved changes')
        self.save_button.set_sensitive(True)
        body=self.body()
        self.length.set_text(f'{len(body):,} characters  ·  {len(body.split()):,} words  ·  Plain text')

    def body(self):
        b=self.text.get_buffer()
        return b.get_text(b.get_start_iter(),b.get_end_iter(),True)

    def guard(self):
        if not self.dirty:
            return True
        d=Gtk.MessageDialog(transient_for=self,modal=True,text='Save your changes?',
            secondary_text='This snippet has edits that have not been saved.')
        d.add_buttons('Keep editing',Gtk.ResponseType.CANCEL,'Discard',Gtk.ResponseType.NO,'Save',Gtk.ResponseType.YES)
        answer=d.run();d.destroy()
        if answer==Gtk.ResponseType.YES:
            return self.save()
        if answer==Gtk.ResponseType.NO:
            self.dirty=False
            return True
        return False

    def refresh_nav(self):
        self.loading=True
        for r in self.nav.get_children():self.nav.remove(r)
        entries=[('All snippets',('all',None)),('★  Favorites',('favorites',None))]
        entries += [(g,('group',g)) for g in self.lib.groups()]
        entries.append(('Trash',('trash',None)))
        for title,value in entries:
            row=Gtk.ListBoxRow();row.value=value
            text=label(title);text.set_margin_start(12);text.set_margin_end(12)
            text.set_margin_top(10);text.set_margin_bottom(10)
            row.add(text);self.nav.add(row)
            if value==self.filter:self.nav.select_row(row)
        self.nav.show_all()
        self.loading=False

    def navigate(self,_box,row):
        if not row or self.loading:return
        if not self.guard():
            self.refresh_nav();return
        self.filter=row.value
        self.current=None
        self.search.set_text('')
        self.list_title.set_text(row.value[1] or {'all':'All snippets','favorites':'Favorites','trash':'Trash'}[row.value[0]])
        self.refresh_list()

    def refresh_list(self,select_id=None):
        self.loading=True
        for row in self.listbox.get_children():self.listbox.remove(row)
        items=self.lib.all(self.filter[0]=='trash')
        if self.filter[0]=='favorites':items=[s for s in items if s['favorite']]
        if self.filter[0]=='group':items=[s for s in items if s['group_name']==self.filter[1]]
        items=[s for s in items if matches(s,self.search.get_text())]
        self.count.set_text(f'{len(items)} snippet'+('' if len(items)==1 else 's'))
        selected=None
        wanted=select_id or (self.current or {}).get('id')
        for s in items:
            row=Gtk.ListBoxRow();row.item=s
            content=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=8,margin=14)
            name=label(('★  ' if s['favorite'] else '')+s['name'],'snippet-name')
            name.set_ellipsize(Pango.EllipsizeMode.END);name.set_max_width_chars(27)
            content.pack_start(name,False,False,0)
            preview=label(' '.join(s['text'].split()),'preview')
            preview.set_ellipsize(Pango.EllipsizeMode.END);preview.set_max_width_chars(30)
            content.pack_start(preview,False,False,0)
            bottom=Gtk.Box(spacing=8)
            tag=label(s['abbreviation'] or 'Quick paste','tag');tag.set_halign(Gtk.Align.START)
            bottom.pack_start(tag,False,False,0)
            if s['note']:bottom.pack_end(label('Review','muted'),False,False,0)
            content.pack_start(bottom,False,False,0)
            row.add(content);self.listbox.add(row)
            if s['id']==wanted:selected=row
        self.listbox.show_all()
        if not selected and items and not self.dirty:selected=self.listbox.get_row_at_index(0)
        if selected:self.listbox.select_row(selected)
        self.loading=False
        if selected and not self.dirty:self.load(selected.item)
        elif not self.dirty:
            self.current=None;self.stack.set_visible_child_name('empty')

    def select(self,_box,row):
        if not row or self.loading:return
        if self.current and row.item['id']==self.current.get('id'):return
        if not self.guard():
            self.refresh_list();return
        self.load(row.item)

    def load(self,item):
        self.loading=True
        self.current=dict(item)
        self.name.set_text(item.get('name',''))
        self.abbr.set_text(item.get('abbreviation',''))
        self.text.get_buffer().set_text(item.get('text',''))
        self.group.remove_all()
        for g in self.lib.groups():self.group.append(g,g)
        self.group.set_active_id(item.get('group_name','General'))
        self.enabled.set_active(bool(item.get('enabled',True)))
        self.favorite.set_active(bool(item.get('favorite')))
        self.note.set_text(item.get('note',''))
        self.note.set_visible(bool(item.get('note')))
        self.delete_button.set_label('Restore snippet' if item.get('deleted') else 'Move to trash')
        self.save_button.set_sensitive(False)
        self.state.set_text('In trash' if item.get('deleted') else 'Saved locally')
        body=item.get('text','')
        self.length.set_text(f'{len(body):,} characters  ·  {len(body.split()):,} words  ·  Plain text')
        self.stack.set_visible_child_name('editor')
        self.dirty=False;self.loading=False

    def save(self,*_):
        if not self.current:return True
        if self.current.get('deleted'):
            message(self,'Restore this snippet first','Choose Restore snippet to edit it again.');return False
        item=dict(self.current,name=self.name.get_text(),text=self.body(),abbreviation=self.abbr.get_text(),
            group_name=self.group.get_active_id() or 'General',favorite=self.favorite.get_active(),enabled=self.enabled.get_active())
        # Review notes remain visible until the user explicitly corrects content and enables it.
        if item['enabled'] and item.get('note'):
            from importers import normalize
            item['note']=normalize(item['name'],item['text'],item['abbreviation'])['note']
            if item['note']:
                message(self,'This snippet still needs conversion',item['note']);return False
        try:
            key=self.lib.save(item,self.current.get('revision'))
        except (ValueError,OSError) as exc:
            message(self,'Could not save',str(exc));return False
        self.dirty=False
        saved=self.lib.get(key)
        self.current=saved
        self.sync()
        self.refresh_nav();self.refresh_list(key)
        self.load(saved)
        return True

    def new(self,*_):
        if not self.guard():return
        self.load(dict(name='',text='',group_name=self.filter[1] if self.filter[0]=='group' else 'General',enabled=True))
        self.dirty=True;self.state.set_text('New snippet');self.save_button.set_sensitive(True)
        self.name.grab_focus()

    def duplicate(self,*_):
        if not self.current or not self.guard():return
        item=dict(self.current,name=self.current['name']+' (copy)',abbreviation='',deleted=0)
        item.pop('id',None);item.pop('revision',None)
        self.load(item);self.dirty=True;self.changed()

    def delete(self,*_):
        if not self.current:return
        if not self.guard():return
        if self.current.get('id'):
            self.lib.trash(self.current['id'],restore=bool(self.current.get('deleted')))
            self.sync()
        self.current=None;self.dirty=False;self.refresh_list()

    def insert_token(self,value):
        self.text.get_buffer().insert_at_cursor(value)
        self.text.grab_focus()

    def copy(self,*_):
        if not self.current:return
        text=render(self.body(),self)
        if text is not None:
            clipboard=Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            clipboard.set_text(text,-1);clipboard.store()
            self.state.set_text('Copied · paste with Alt + V')

    def new_group(self,*_):
        if not self.guard():return
        d=Gtk.Dialog(title='New group',transient_for=self,modal=True)
        d.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Create group',Gtk.ResponseType.OK)
        field=Gtk.Entry(placeholder_text='e.g. Customer support',margin=20,activates_default=True)
        d.set_default_response(Gtk.ResponseType.OK)
        d.get_content_area().add(field);d.show_all()
        if d.run()==Gtk.ResponseType.OK and field.get_text().strip():
            self.lib.add_group(field.get_text())
            self.filter=('group',field.get_text().strip());self.current=None
            self.refresh_nav();self.list_title.set_text(field.get_text().strip());self.refresh_list()
        d.destroy()

    def sync(self):
        try:integration.sync(self.lib)
        except OSError as exc:message(self,'Saved; typed expansion needs attention',str(exc))

    def toggle_pause(self,*_):
        self.lib.set_setting('paused','yes' if self.pause.get_active() else 'no');self.sync()

    def import_dialog(self,*_):
        if not self.guard():return
        dialog=Gtk.FileChooserDialog(title='Import TextExpander snippets',transient_for=self,
            action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Preview import',Gtk.ResponseType.OK)
        dialog.set_select_multiple(True)
        dialog.set_current_folder(str(Path.home()/'Downloads'))
        f=Gtk.FileFilter();f.set_name('Snippet files (CSV, JSON, TextExpander)')
        for pattern in ('*.csv','*.tsv','*.json','*.textexpander','*.plist'):f.add_pattern(pattern)
        dialog.add_filter(f)
        response=dialog.run();paths=dialog.get_filenames();dialog.destroy()
        if response!=Gtk.ResponseType.OK:return
        try:
            items=[]
            for path in paths:items.extend(parse_file(path))
        except Exception as exc:
            message(self,'Import could not be read',str(exc));return
        self.preview_import(items)

    def preview_import(self,items):
        dialog=Gtk.Dialog(title='Review your import',transient_for=self,modal=True)
        dialog.set_default_size(780,520)
        dialog.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Import snippets',Gtk.ResponseType.OK)
        box=dialog.get_content_area();box.set_border_width(20);box.set_spacing(14)
        box.pack_start(label(f'{len(items)} snippets ready to review','section-title'),False,False,0)
        hint=label('Exact duplicates are skipped. Items with unsupported formatting or macros stay disabled.','muted')
        hint.set_line_wrap(True);box.pack_start(hint,False,False,0)
        model=Gtk.ListStore(str,str,str,str)
        for item in items:model.append([item['name'],item['abbreviation'],item['group_name'],item['note'] or 'Ready'])
        tree=Gtk.TreeView(model=model)
        for n,title in enumerate(('Name','Abbreviation','Group','Status')):
            renderer=Gtk.CellRendererText();renderer.set_property('ellipsize',Pango.EllipsizeMode.END)
            col=Gtk.TreeViewColumn(title,renderer,text=n);col.set_resizable(True)
            col.set_max_width(260);tree.append_column(col)
        scroll=Gtk.ScrolledWindow();scroll.add(tree);box.pack_start(scroll,True,True,0)
        details=label('Select an item to see its full review note.','muted')
        details.set_line_wrap(True);details.set_max_width_chars(90)
        def inspect(selection):
            m,it=selection.get_selected()
            if it:details.set_text(m[it][3])
        tree.get_selection().connect('changed',inspect)
        box.pack_start(details,False,False,0)
        prefix=Gtk.Entry(placeholder_text='Optional abbreviation prefix, e.g. ;')
        box.pack_start(prefix,False,False,0)
        enable=Gtk.CheckButton(label='Enable compatible abbreviations after import');enable.set_active(True)
        box.pack_start(enable,False,False,0)
        dialog.show_all();response=dialog.run()
        enabled=enable.get_active();prefix_value=prefix.get_text();dialog.destroy()
        if response!=Gtk.ResponseType.OK:return
        for item in items:
            if item['abbreviation']:item['abbreviation']=prefix_value+item['abbreviation']
            if not enabled:item['enabled']=False
        try:added,duplicates,review=self.lib.import_items(items)
        except Exception as exc:message(self,'Import failed',str(exc));return
        self.sync();self.filter=('all',None);self.current=None
        self.list_title.set_text('All snippets');self.search.set_text('')
        self.refresh_nav();self.refresh_list()
        message(self,'Import complete',f'{added} added · {duplicates} duplicates skipped · {review} need review.\nYour previous library was backed up automatically.')

    def export_dialog(self,*_):
        if not self.guard():return
        d=Gtk.FileChooserDialog(title='Export library',transient_for=self,action=Gtk.FileChooserAction.SAVE)
        d.add_buttons('Cancel',Gtk.ResponseType.CANCEL,'Export',Gtk.ResponseType.OK)
        d.set_do_overwrite_confirmation(True);d.set_current_name('Snippets.json')
        d.set_current_folder(str(Path.home()/'Downloads'))
        for pattern,title in [('*.json','Snippets JSON — includes all settings'),('*.csv','CSV — names, abbreviations, text and groups')]:
            f=Gtk.FileFilter();f.set_name(title);f.add_pattern(pattern);d.add_filter(f)
        if d.run()==Gtk.ResponseType.OK:
            path=d.get_filename()
            try:
                self.lib.export(path)
                message(self,'Library exported',path)
            except OSError as exc:message(self,'Could not export',str(exc))
        d.destroy()

    def help_dialog(self,*_):
        message(self,'A little less typing, every day',
            'QUICK PASTE\nClick in a text field, press Ctrl + ., search and press Enter. Esc cancels.\n\n'
            'TYPED EXPANSION\nGive a snippet an abbreviation such as ;thanks. Save, then type it in another app. '
            'Use Pause typed expansion to temporarily disable abbreviations.\n\n'
            'PERSONALIZE\nUse {{name}} for a fill-in, {{date}} for today, {{time}} for the time, or {{clipboard}}.\n\n'
            'IMPORT FROM TEXTEXPANDER\nIn TextExpander.com open Import / Export → Export and download each group as CSV. '
            'Import those files here. Plain text, labels and abbreviations are supported. Rich text, images, scripts, '
            'nested snippets and TextExpander-specific macros require conversion; flagged imports remain disabled. '
            'Use an optional prefix if your old group had one.\n\n'
            'YOUR DATA\nStored locally, with automatic backups before edits and imports. Trash is recoverable. '
            'Export JSON for a portable backup. Desktop expansion uses AutoKey on your X11 session.')

    def keys(self,_w,event):
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            key=Gdk.keyval_name(event.keyval).lower()
            if key=='s':self.save();return True
            if key=='n':self.new();return True
            if key=='f':self.search.grab_focus();return True
        return False

    def check_external(self):
        if not self.get_visible():return False
        version=self.lib.db.execute('PRAGMA data_version').fetchone()[0]
        if version!=self.version and not self.dirty:
            self.version=version;self.refresh_nav();self.refresh_list()
        return True


class App(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='com.bizon.Snippets',flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window=None

    def do_activate(self):
        if not self.window:
            style()
            self.window=MainWindow(self)
            self.window.sync()
            self.window.connect('destroy',lambda *_:setattr(self,'window',None))
        self.window.present()


if __name__=='__main__':
    os.umask(0o077)
    App().run(sys.argv)
