"""Executed inside AutoKey. Restore the original window before pasting."""
import fcntl
import json
import os
import subprocess
import time
from pathlib import Path


def run(keyboard, clipboard, window, snippet_id=None, abbreviation=''):
    runtime=Path(os.environ.get('XDG_RUNTIME_DIR',str(Path.home()/'.cache')))
    with (runtime/'bizon-snippet-picker.lock').open('w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return
        target=subprocess.check_output(['/usr/bin/xdotool','getactivewindow'],text=True).strip()
        app_class=window.get_active_class().lower()
        if snippet_id and ('bizonsnippets' in app_class or 'bizon-snippets' in app_class):
            return
        if snippet_id and abbreviation:
            keyboard.send_key('<backspace>',repeat=len(abbreviation))
        env=os.environ.copy()
        for key in ('LD_LIBRARY_PATH','LD_PRELOAD','PYTHONHOME','PYTHONPATH'):env.pop(key,None)
        command=['/usr/bin/python3',str(Path(__file__).with_name('picker.py'))]
        if snippet_id:command+=['--expand',snippet_id]
        result=subprocess.run(command,capture_output=True,text=True,env=env)
        content=None
        if result.returncode==0 and result.stdout.strip():
            content=json.loads(result.stdout)['text']
        elif abbreviation:
            # Put the trigger back if a fill-in was cancelled.
            content=abbreviation
        if content is None:return
        clipboard.fill_clipboard(content)
        try:
            subprocess.run(['/usr/bin/xdotool','windowactivate','--sync',target],check=True,timeout=3,capture_output=True)
            time.sleep(.15)
            active=subprocess.check_output(['/usr/bin/xdotool','getactivewindow'],text=True).strip()
            if active!=target:return
            terminals=('gnome-terminal','kgx','tilix','terminator','xfce4-terminal','mate-terminal','konsole','alacritty','kitty','wezterm')
            modifier='<ctrl>+<shift>+' if any(t in app_class for t in terminals) else '<ctrl>+'
            keyboard.send_keys(modifier+'v')
        except (subprocess.SubprocessError,OSError):
            pass


if 'keyboard' in globals():
    run(keyboard,clipboard,window,globals().get('snippet_id'),globals().get('abbreviation',''))
