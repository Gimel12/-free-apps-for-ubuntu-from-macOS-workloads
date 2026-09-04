"""Manage only our own AutoKey folder; preserve unrelated user shortcuts."""
import json
import os
from pathlib import Path

APP = Path(__file__).resolve().parent


def write_atomic(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(text)
    temp.chmod(0o600)
    temp.replace(path)


def config(name, abbr=None, hotkey=False):
    return {'type':'script', 'description':name, 'store':{}, 'modes':[3] if hotkey else [1],
            'usageCount':0, 'prompt':False, 'omitTrigger':True, 'showInTrayMenu':False,
            'abbreviation':{'abbreviations':[abbr] if abbr else [], 'backspace':False,
                'ignoreCase':False, 'immediate':True, 'triggerInside':False, 'wordChars':'[\\w]'},
            'hotkey':{'modifiers':['<ctrl>'] if hotkey else [], 'hotKey':'.' if hotkey else None},
            'filter':{'regex':None,'isRecursive':False}}


def bridge_code(key=None, abbreviation=''):
    return ('import runpy\nrunpy.run_path(' + repr(str(APP/'bridge.py')) + ', init_globals={'
            + "'keyboard':keyboard,'clipboard':clipboard,'window':window,'snippet_id':"
            + repr(key) + ",'abbreviation':" + repr(abbreviation) + '})\n')


def sync(library, root=None):
    root = Path(root) if root else Path.home()/'.config/autokey/data'
    folder = root/'Bizon Snippet Expansions'
    folder.mkdir(parents=True, exist_ok=True)
    meta = config('Bizon Snippet Expansions')
    meta.update(type='folder',title='Bizon Snippet Expansions',modes=[])
    write_atomic(folder/'.folder.json', json.dumps(meta,indent=2))
    wanted = set()
    if library.setting('paused') != 'yes':
        for s in library.all():
            if not s['enabled'] or not s['abbreviation']:
                continue
            # Database IDs become local filenames; generated/imported IDs are not used as paths.
            import hashlib
            base = 'snippet-' + hashlib.sha256(s['id'].encode()).hexdigest()[:24]
            script = folder/(base+'.py')
            metadata = folder/('.'+base+'.json')
            write_atomic(metadata, json.dumps(config(s['name'], s['abbreviation']),indent=2))
            write_atomic(script, bridge_code(s['id'],s['abbreviation']))
            wanted.update((script,metadata))
    for path in list(folder.glob('snippet-*.py')) + list(folder.glob('.snippet-*.json')):
        if path not in wanted:
            path.unlink()
