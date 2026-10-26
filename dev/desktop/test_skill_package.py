"""A share archive contains public files and a relative-path integrity manifest."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location('build_skill', Path(__file__).with_name('build_skill.py'))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class SkillPackageTests(unittest.TestCase):
    def test_public_diagnostic_code_is_kept_but_user_evidence_is_excluded(self):
        self.assertTrue(builder.distributable(Path('src/looktool/jobdiagnostics.py')))
        for path in ('settings.private.json', 'log/worker.txt', 'diagnostics.zip', 'camera.ARW', 'source.DAT'):
            self.assertFalse(builder.distributable(Path(path)), path)

    def test_manifest_has_only_relative_public_members_and_no_old_self_entry(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / 'skill'
            package.mkdir()
            (package / 'SKILL.md').write_text('skill', encoding='utf-8')
            (package / 'package-manifest.json').write_text('old manifest', encoding='utf-8')
            output = root / 'share.zip'
            builder.archive_package(package, output)
            with zipfile.ZipFile(output) as archive:
                manifest = json.loads(archive.read('a7c2-fuji-install/package-manifest.json'))
                self.assertEqual([r['path'] for r in manifest['files']], ['SKILL.md'])
                self.assertEqual(sorted(archive.namelist()), ['a7c2-fuji-install/SKILL.md', 'a7c2-fuji-install/package-manifest.json'])
            self.assertTrue(output.with_suffix('.zip.sha256').is_file())

    def test_private_state_stops_archiving(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'settings.private.json').write_text('private', encoding='utf-8')
            with self.assertRaises(ValueError):
                builder.archive_package(root, root.parent / 'forbidden.zip')
