"""Portable launcher preserves per-user progress without source dependencies."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from desktopapp import guide, skillentry
from desktopapp.paths import write_json


class SkillEntryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        environment = patch.dict(os.environ, {'A7C2_DESKTOP_DATA': str(self.root)})
        environment.start()
        self.addCleanup(environment.stop)

    def test_init_stores_new_session_then_resumes_without_reinitializing(self):
        calls = []
        def run(arguments):
            calls.append(arguments)
            print(json.dumps({'session': str(self.root / 'session'), 'phase': 'CAMERA_INFO'}))
            return 0
        with patch.object(guide, 'main', side_effect=run), redirect_stdout(io.StringIO()):
            self.assertEqual(skillentry.main(['init']), 0)
            self.assertEqual(skillentry.main(['init']), 0)
        self.assertEqual(calls, [['init'], ['--session', str(self.root / 'session'), 'status']])
        self.assertEqual(guide.read(skillentry.settings_path()), {'session': str(self.root / 'session')})

    def test_failed_init_does_not_create_saved_progress(self):
        def fail(arguments):
            print(json.dumps({'ok': False, 'error': 'missing assets'}))
            return 2
        with patch.object(guide, 'main', side_effect=fail), redirect_stdout(io.StringIO()):
            self.assertEqual(skillentry.main(['init']), 2)
        self.assertFalse(skillentry.settings_path().exists())

    def test_unreadable_saved_progress_stops_without_new_init(self):
        path = skillentry.settings_path()
        path.parent.mkdir(parents=True)
        path.write_text('not json', encoding='utf-8')
        with patch.object(guide, 'main') as run, redirect_stdout(io.StringIO()):
            self.assertEqual(skillentry.main(['init']), 2)
        run.assert_not_called()
        self.assertEqual(path.read_text(encoding='utf-8'), 'not json')

    def test_internal_worker_and_explicit_session_are_forwarded_unchanged(self):
        arguments = ['_worker', '--request', 'request.json', '--backend', 'A7C2Tools.exe']
        with patch.object(guide, 'main', return_value=2) as run:
            self.assertEqual(skillentry.main(arguments), 2)
        run.assert_called_once_with(arguments)

    def test_upgrade_adopts_only_the_local_legacy_session(self):
        executable = self.root / 'skill/assets/runtime/guide/A7C2Guide.exe'
        write_json(self.root / 'skill/settings.private.json', {'session': 'previous-session', 'project': 'old-checkout'})
        with patch.object(skillentry.sys, 'frozen', True, create=True), patch.object(skillentry.sys, 'executable', str(executable)):
            self.assertEqual(skillentry.saved_settings(), {'session': 'previous-session'})
