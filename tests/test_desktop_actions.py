"""Verify user shortcuts survive installation and conflicting keywords are rejected."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('desktop_actions_install', ROOT / 'apps/desktop-actions/install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class DesktopActionsTest(unittest.TestCase):
    def test_reinstall_preserves_unrelated_shortcuts_and_backs_up(self):
        with tempfile.TemporaryDirectory(prefix='desktop-actions-') as folder:
            home = Path(folder)
            config = home / '.config/ulauncher/shortcuts.json'
            config.parent.mkdir(parents=True)
            existing = {'unrelated': {'keyword': 'find', 'cmd': 'https://example.org/?q=%s'}}
            config.write_text(json.dumps(existing))
            with patch.dict(os.environ, {'HOME': str(home), 'XDG_CONFIG_HOME': str(home / '.config')}), \
                 patch.object(sys, 'argv', ['install.py']), \
                 patch.object(installer.os, 'getuid', return_value=1000), \
                 patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)) as run:
                installer.main()
                first = json.loads(config.read_text())
                installer.main()
                second = json.loads(config.read_text())
            self.assertEqual(first, second)
            self.assertEqual(second['unrelated'], existing['unrelated'])
            self.assertEqual(len(second), 5)
            self.assertEqual(len(list(config.parent.glob('shortcuts-before-*.json'))), 2)
            self.assertIn(str(home), second[installer.ACTIONS[-1][0]]['cmd'])
            self.assertTrue((home / '.local/lib/desktop-actions/quit_all_apps.py').exists())
            self.assertTrue(all(call.args[0][0] == 'pgrep' for call in run.call_args_list))

    def test_keyword_collision_preserves_input(self):
        original = {'other': {'keyword': 'shutdown', 'cmd': 'custom command'}}
        with self.assertRaises(ValueError):
            installer.merged_shortcuts(original, Path('/tmp/example'))
        self.assertEqual(original['other']['cmd'], 'custom command')

    def test_running_ulauncher_blocks_config_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(os.environ, {'HOME': folder, 'XDG_CONFIG_HOME': folder}), \
                 patch.object(sys, 'argv', ['install.py']), \
                 patch.object(installer.os, 'getuid', return_value=1000), \
                 patch.object(installer.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                with self.assertRaises(SystemExit):
                    installer.main()
            self.assertFalse((Path(folder) / 'ulauncher/shortcuts.json').exists())


if __name__ == '__main__':
    unittest.main()
