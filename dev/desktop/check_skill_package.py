"""Verify a standalone ZIP and smoke-test only offline commands after relocation."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import zipfile


def check(archive_path, report_path):
    archive_path = Path(archive_path).resolve()
    with tempfile.TemporaryDirectory(prefix='A7C2 中文 离线检查 ') as temporary:
        root = Path(temporary)
        data = root / 'user-data'
        with zipfile.ZipFile(archive_path) as archive:
            prefix = 'a7c2-fuji-install/'
            manifest = json.loads(archive.read(prefix + 'package-manifest.json'))
            assert manifest['schema'] == 'a7c2-skill-package/1'
            preset_only = manifest.get('flavor') == 'preset-only'
            expected = {prefix + row['path']: row for row in manifest['files']}
            assert set(archive.namelist()) == {*expected, prefix + 'package-manifest.json'}
            for name in archive.namelist():
                path = PurePosixPath(name)
                assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
                assert '.private.' not in name.lower() and '/log/' not in name.lower()
                with archive.open(name) as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                if name in expected:
                    assert digest == expected[name]['sha256'], name
                # Relocate the standalone frontend and all look files. The real
                # camera backend is not executed in this offline smoke test.
                if (name.startswith(prefix + 'assets/runtime/guide/')
                        or name.startswith(prefix + 'assets/runtime/backend/Profiles/')
                        or name.startswith(prefix + 'scripts/')
                        or name in {prefix + 'assets/runtime/backend/A7C2Tools.exe',
                                    prefix + 'assets/runtime/backend/_internal/python311.dll'}):
                    archive.extract(name, root)
        skill = root / 'a7c2-fuji-install'
        executable = skill / 'assets/runtime/guide/A7C2Guide.exe'
        environment = dict(os.environ, A7C2_DESKTOP_DATA=str(data), PYTHONPATH='', PYTHONHOME='',
                           PATH=str(Path(os.environ['SystemRoot']) / 'System32'))
        def run(arguments, expected_code=0):
            result = subprocess.run([str(executable), *arguments], cwd=root, env=environment,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    encoding='utf-8', timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
            assert result.returncode == expected_code, result.stderr + result.stdout
            return json.loads(result.stdout)
        doctor = run(['doctor'])
        assert doctor['ok'] and doctor['profiles'] == 15 and not doctor['camera_io']
        if preset_only:
            assert not (skill / 'assets/runtime/backend').exists()
            assert run(['doctor', '--native-check'])['native_check']['native_workers_compiled'] == 4
        initial = run(['init'])
        assert initial['phase'] == 'CAMERA_INFO'
        if preset_only:
            assert initial['preset_only'] and not initial['alternatives']['extras']
        assert [r['profile'] for r in initial['plan']['looks']] == [
            'Classic Neg.', 'Classic Chrome', 'Nostalgic Neg.', 'Velvia', 'GR Positive Film', 'GR Negative Film']
        session = initial['session']
        assert run(['init'])['session'] == session
        review = run(['--session', session, 'review'])['review']
        assert review['decision'] == 'NO_RECONCILIATION_NEEDED' and not review['can_apply']
        config = root / 'custom.json'
        config.write_text(json.dumps({'looks': [{'slot': 1, 'profile': 'Eterna'}, {'slot': 6, 'profile': 'GR Vivid'}]}), encoding='utf-8')
        custom = run(['--session', session, 'configure', '--file', str(config)])
        assert custom['plan']['replaces_slots'] == [1, 6]
        assert run(['init'])['plan']['id'] == custom['plan']['id']
        if preset_only:
            config.write_text(json.dumps({'extras': {'sound': True}}), encoding='utf-8')
            assert not run(['--session', session, 'configure', '--file', str(config)], 2)['ok']
            assert run(['init'])['plan']['id'] == custom['plan']['id']
        config.write_text(json.dumps({'looks': [{'slot': i, 'profile': 'Eterna'} for i in range(1, 8)]}), encoding='utf-8')
        assert run(['--session', session, 'configure', '--file', str(config)], 2)['ok'] is False
        assert run(['init'])['plan']['id'] == custom['plan']['id']
        shell = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
        command = "& '" + str(skill / 'scripts/guide.cmd').replace("'", "''") + "' doctor"
        launched = subprocess.run([str(shell), '-NoProfile', '-NonInteractive', '-Command', command], cwd=root,
                                 env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 encoding='utf-8', timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        assert launched.returncode == 0, launched.stderr + launched.stdout
        launched_value = json.loads(launched.stdout)
        assert launched_value['profiles'] == 15
        settings = 'ai-skill-presets' if preset_only else 'ai-skill'
        assert launched_value['settings'] == str(data / settings / 'settings.private.json'), launched.stdout
        report = dict(archive=archive_path.name, verified_files=len(expected), camera_io=False,
                      relocated_unicode_space_path=True, external_python_not_on_path=True,
                      profiles=15, default_plan=True, custom_plan=True, resume_preserved=True,
                      seventh_slot_rejected=True, windows_cmd_launcher=True, offline_review_available=True)
        if preset_only:
            report.update(preset_only=True, native_workers_compiled=4, extra_features_rejected=True,
                          desktop_gui_bundled=False, source_profile_payloads_preserved=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    arguments = parser.parse_args()
    check(arguments.archive, arguments.report)
