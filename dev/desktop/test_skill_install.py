"""Standalone installation verifies package members and preserves local state."""
from contextlib import redirect_stdout, redirect_stderr
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('install_guide_skill', Path(__file__).with_name('install_guide_skill.py'))
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class SkillInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.package, self.target = self.root / 'package', self.root / 'installed'
        self.rows = []
        for relative in ('SKILL.md', 'scripts/guide.cmd', 'assets/runtime/guide/A7C2Guide.exe',
                         'assets/runtime/backend/A7C2Tools.exe', 'assets/runtime/backend/Profiles/catalog.json'):
            path = self.package / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'fixture; not executable')
            self.rows.append(dict(path=relative, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        self.write_manifest()

    def write_manifest(self):
        (self.package / 'package-manifest.json').write_text(json.dumps(dict(schema='a7c2-skill-package/1', files=self.rows)), encoding='utf-8')

    def install(self):
        with patch.object(sys, 'argv', ['install', '--package', str(self.package), '--destination', str(self.target)]), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            installer.main()

    def test_install_preserves_local_progress_and_does_not_copy_unlisted_private_files(self):
        self.target.mkdir()
        local = self.target / 'settings.private.json'
        local.write_bytes(b'existing progress')
        (self.package / 'settings.private.json').write_bytes(b'another camera')
        self.install()
        self.assertEqual(local.read_bytes(), b'existing progress')
        self.assertEqual((self.target / 'SKILL.md').read_bytes(), b'fixture; not executable')

    def test_bad_checksum_stops_before_copying_any_member(self):
        (self.package / 'SKILL.md').write_bytes(b'changed')
        with self.assertRaises(SystemExit):
            self.install()
        self.assertFalse(self.target.exists())

    def test_traversal_manifest_is_rejected_before_copying(self):
        self.rows.append(dict(path='../outside', sha256='0' * 64))
        self.write_manifest()
        with self.assertRaises(SystemExit):
            self.install()
        self.assertFalse(self.target.exists())
