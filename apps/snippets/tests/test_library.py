import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from library import Library, Conflict, matches
from importers import parse_file
from integration import sync
from bridge import run


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.lib=Library(self.root)

    def tearDown(self):
        self.lib.db.close();self.temp.cleanup()

    def test_existing_picker_migration_preserves_text(self):
        self.lib.db.close()
        self.lib.path.unlink()
        text='Thanks and if any questions, please let me know.'
        (self.root/'snippets.json').write_text(json.dumps({'snippets':[{'id':'thanks','name':'Thanks','text':text}]}))
        self.lib=Library(self.root)
        self.assertEqual(self.lib.get('thanks')['text'],text)
        self.assertEqual(self.lib.get('thanks')['abbreviation'],';thanks')
        second=Library(self.root)
        self.assertEqual(len(second.all()),1)
        second.db.close()

    def test_edit_conflict_trash_restore_and_backup(self):
        key=self.lib.save(dict(name='Hello',text='One',abbreviation=';hi'))
        original=self.lib.get(key)
        self.lib.save(dict(original,text='Two'),original['revision'])
        with self.assertRaises(Conflict):self.lib.save(dict(original,text='Stale'),original['revision'])
        self.assertEqual(self.lib.get(key)['text'],'Two')
        self.lib.trash(key)
        self.assertEqual(self.lib.all(),[])
        self.lib.trash(key,True)
        self.assertFalse(self.lib.get(key)['enabled'])
        self.assertTrue(list((self.root/'backups').glob('*.sqlite3')))

    def test_abbreviation_overlap_rejected(self):
        self.lib.save(dict(name='Thanks',text='Hello',abbreviation=';thanks'))
        with self.assertRaises(Conflict):self.lib.save(dict(name='Short',text='Other',abbreviation=';th'))

    def test_textexpander_multiline_csv_and_headerless(self):
        p=self.root/'Support.csv'
        p.write_text('abbreviation,content,label\r\n;hello,"Hello,\n\"\"Pat\"\"!",Greeting\r\n')
        items=parse_file(p)
        self.assertEqual(items[0]['text'],'Hello,\n"Pat"!')
        self.assertEqual(items[0]['group_name'],'Support')
        p.write_text(';thanks,"Thank you,\nGoodbye",Thanks\n')
        self.assertEqual(parse_file(p)[0]['name'],'Thanks')

    def test_import_duplicate_collision_macros_and_rollback(self):
        self.lib.save(dict(name='Existing',text='Existing body',abbreviation=';same'))
        p=self.root/'Test.csv'
        p.write_text('abbreviation,content,label\n;same,New body,Collision\n;fill,%filltext:name=Name%,Template\n')
        items=parse_file(p)
        self.assertEqual(self.lib.import_items(items),(2,0,2))
        self.assertEqual(self.lib.import_items(items),(0,2,0))
        self.assertFalse(next(s for s in self.lib.all() if s['name']=='Collision')['enabled'])
        before=len(self.lib.all())
        with self.assertRaises(ValueError):self.lib.import_items([dict(name='Good',text='Okay'),dict(name='',text='')])
        self.assertEqual(len(self.lib.all()),before)

    def test_json_and_plist_and_export(self):
        key=self.lib.save(dict(name='Unicode ✓',text='Hi\n世界',abbreviation=';world',favorite=True))
        p=self.root/'Backup.json';self.lib.export(p)
        self.assertTrue(parse_file(p)[0]['favorite'])
        p=self.root/'Legacy.textexpander'
        p.write_bytes(plistlib.dumps({'groupName':'Sales','snippets':[{'label':'Hi','abbreviation':';hi','plainText':'Hello'}]}))
        self.assertEqual(parse_file(p)[0]['group_name'],'Sales')

    def test_expansion_files_and_autokey_trigger(self):
        key=self.lib.save(dict(name='Thanks',text='Literal <ctrl>+v',abbreviation=';thanks'))
        root=self.root/'autokey';sync(self.lib,root)
        folder=root/'Bizon Snippet Expansions'
        files=list(folder.glob('snippet-*.py'))
        self.assertEqual(len(files),1)
        compile(files[0].read_text(),str(files[0]),'exec')
        import gi
        gi.require_version('Gtk','3.0');gi.require_version('Gdk','3.0')
        from autokey import common
        common.USING_QT=False
        from autokey.iomediator import IoMediator
        from autokey.model import Script, Folder
        parent=Folder('Bizon Snippet Expansions',path=str(folder));parent.load()
        script=next(item for item in parent.items if isinstance(item,Script))
        self.assertEqual(script.process_buffer(';thanks'),(0,''))
        self.assertTrue(script._should_trigger_abbreviation(';thanks'))
        self.lib.set_setting('paused','yes');sync(self.lib,root)
        self.assertFalse(list(folder.glob('snippet-*.py')))

    def test_search_full_text_and_abbreviation(self):
        self.assertTrue(matches(dict(name='Thanks',text='Please let me know.',abbreviation=';thanks',group_name='Support'),'SUPPORT know'))


class BridgeTests(unittest.TestCase):
    def exercise(self,text,active='123',abbr='',kind='Chrome'):
        keyboard=Mock();clipboard=Mock();window=Mock();window.get_active_class.return_value=kind
        output=json.dumps({'text':text}) if text is not None else ''
        def fake(args,**kw):return subprocess.CompletedProcess(args,0,output if args[0]=='/usr/bin/python3' else '')
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'XDG_RUNTIME_DIR':d}),patch('subprocess.run',side_effect=fake),patch('subprocess.check_output',side_effect=['123',active]),patch('time.sleep'):
            run(keyboard,clipboard,window,'id' if abbr else None,abbr)
        return keyboard,clipboard

    def test_paste_is_literal_and_never_enter(self):
        keys,clip=self.exercise('Thanks <ctrl>+x\n$HOME')
        keys.send_keys.assert_called_once_with('<ctrl>+v')
        clip.fill_clipboard.assert_called_once_with('Thanks <ctrl>+x\n$HOME')

    def test_focus_changed_cancel_and_terminal(self):
        keys,_=self.exercise('Hello','456');keys.send_keys.assert_not_called()
        keys,_=self.exercise(None);keys.send_keys.assert_not_called()
        keys,clip=self.exercise(None,abbr=';hi');clip.fill_clipboard.assert_called_once_with(';hi')
        keys,_=self.exercise('hello',kind='gnome-terminal');keys.send_keys.assert_called_once_with('<ctrl>+<shift>+v')

    def test_never_expand_inside_our_own_editor(self):
        keys,clip=self.exercise('hello',abbr=';hi',kind='bizon-snippets.BizonSnippets')
        keys.send_keys.assert_not_called();keys.send_key.assert_not_called()
        clip.fill_clipboard.assert_not_called()


if __name__=='__main__':unittest.main()
