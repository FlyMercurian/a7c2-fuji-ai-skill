"""Human gates, persisted execution boundaries and offline-only guide commands."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

from desktopapp import guide
from desktopapp.paths import write_json


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.env = patch.dict(os.environ, {'A7C2_DESKTOP_DATA': str(self.root / 'app')})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.backend = self.root / 'package/A7C2Tools.exe'
        self.backend.parent.mkdir()
        (self.backend.parent / '_internal').mkdir()
        self.backend.write_bytes(b'not an executable; never launch in tests')
        self.library = self.root / 'profiles'
        self.library.mkdir()
        self.asset_mock = patch.object(guide, 'assets', side_effect=self.fake_assets)
        self.asset_mock.start()
        self.addCleanup(self.asset_mock.stop)
        self.session = self.root / 'app/ai-guide/session'
        guide.initialize(self.session, self.backend, self.library)
        self.state, self.path = guide.load(self.session)
        self.spawn = Mock(return_value=Mock(pid=987654))

    def fake_assets(self, library, selection):
        rows = []
        for selected in selection:
            profile = selected['profile']
            path = Path(library) / (profile + '.a7look')
            if not path.exists():
                path.write_text(json.dumps(dict(name=profile)), encoding='utf-8')
            rows.append(dict(slot=selected['slot'], profile=profile, name=profile,
                             path=str(path), sha256=guide.digest(path.read_bytes())))
        return rows, [dict(name=name, category='Ricoh GR III' if name.startswith('GR ') else 'Fujifilm')
                      for name in guide.DEFAULTS]

    def camera(self, version='2.01', modified='no'):
        guide.answer(self.state, 'camera', dict(model='ILCE-7CM2', firmware=version, modified=modified))

    def prepare(self, modified='no'):
        self.camera(modified=modified)
        guide.answer(self.state, 'connected', dict(confirmed=True))
        self.launch('drivers')
        self.finish({})
        self.launch('stability')
        self.finish(dict(phase='PASSED', camera_io_ended=True))

    def launch(self, operation, **values):
        guide.start(self.state, self.path, operation, values, spawn=self.spawn)

    def finish(self, result, success=True, ended=True):
        job = Path(self.state['active']['job'])
        write_json(job / 'status.private.json', dict(phase='SUCCEEDED' if success else 'FAILED',
                                                     result=result, error='ambiguous result' if not success else ''))
        if ended:
            write_json(job / 'execution.private.json', dict(phase='ENDED', worker_started=True,
                                                            returncode=0 if success else 2))
        guide.poll(self.state)

    def test_old_or_new_unsupported_firmware_cannot_open_camera(self):
        for version, expected in [('1.02', 'FIRMWARE_UPDATE'), ('3.00', 'UNSUPPORTED_FIRMWARE'),
                                  ('unknown', 'UNSUPPORTED_FIRMWARE'), ('', 'UNSUPPORTED_FIRMWARE')]:
            self.state['phase'] = 'CAMERA_INFO'
            self.camera(version)
            self.assertEqual(self.state['phase'], expected)
            with self.assertRaises(ValueError):
                self.launch('drivers')
        self.spawn.assert_not_called()

    def test_default_is_requested_fuji_ricoh_mix_without_extras_and_initialization_is_offline(self):
        self.assertEqual([r['profile'] for r in self.state['plan']['looks']],
                         ['Classic Neg.', 'Classic Chrome', 'Nostalgic Neg.', 'Velvia',
                          'GR Positive Film', 'GR Negative Film'])
        self.assertFalse(any(self.state['extras'].values()))
        self.spawn.assert_not_called()
        before = self.path.read_bytes()
        self.assertEqual(guide.view(self.state)['phase'], 'CAMERA_INFO')
        self.assertEqual(before, self.path.read_bytes())

    def test_updated_defaults_do_not_replace_a_saved_plan(self):
        original = dict(looks=[dict(slot=2, profile='Astia'), dict(slot=5, profile='GR Vivid')])
        guide.configure(self.state, original)
        guide.save(self.state, self.path)
        saved_plan = self.state['plan']
        with patch.object(guide, 'DEFAULTS', ('Eterna',)):
            loaded, _ = guide.load(self.session)
            result = guide.view(loaded)
        self.assertEqual(result['plan'], saved_plan)
        self.assertEqual(result['plan']['replaces_slots'], [2, 5])
        self.spawn.assert_not_called()

    def test_frozen_guide_starts_its_own_worker_without_a_source_checkout(self):
        self.camera()
        guide.answer(self.state, 'connected', dict(confirmed=True))
        portable = str(self.root / 'portable/guide/A7C2Guide.exe')
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', portable):
            self.launch('drivers')
        command = self.spawn.call_args.args[0]
        self.assertEqual(command[:2], [portable, '_worker'])
        self.assertNotIn(str(guide.ROOT / 'ai_guide.py'), command)

    def test_install_requires_actual_battery_and_slot_replacement_acceptance(self):
        self.prepare()
        for values in ({}, {'confirmed': True}, {'confirmed': True, 'battery': 49, 'replace_slots': True},
                       {'confirmed': True, 'battery': 80}, {'confirmed': True, 'battery': True, 'replace_slots': True}):
            with self.assertRaises(ValueError):
                self.launch('install', **values)
        self.assertEqual(self.state['phase'], 'READY_INSTALL')
        self.assertEqual(self.spawn.call_count, 2)  # Only drivers and read-only stability.

    def test_full_default_flow_writes_once_and_requires_human_checks(self):
        self.prepare()
        self.launch('install', confirmed=True, battery=85, replace_slots=True)
        original_job = Path(self.state['active']['job'])
        request = guide.read(original_job / 'request.private.json')
        self.assertEqual(request['action'], 'setup_all')
        options = request['arguments']['options']
        self.assertEqual([row['slot'] for row in options['looks']], list(range(1, 7)))
        self.assertTrue(all(options[key] is False for key in guide.EXTRAS))
        for source, frozen in zip(self.state['plan']['looks'], options['looks']):
            self.assertEqual(Path(source['path']).read_bytes(), Path(frozen['path']).read_bytes())
        self.finish(dict(phase='WAIT_RELOAD', workspace=request['arguments']['workspace']))
        self.assertEqual(self.state['phase'], 'WAIT_RELOAD')
        self.assertIn('cold_reload_steps', guide.view(self.state))
        with self.assertRaises(ValueError):
            self.launch('install', confirmed=True, battery=80, replace_slots=True)
        guide.answer(self.state, 'reboot', dict(confirmed=True))
        self.launch('continue', confirmed=True, battery=80)
        resumed = guide.read(Path(self.state['active']['job']) / 'request.private.json')
        self.assertEqual(resumed['arguments'], request['arguments'])
        self.finish(dict(phase='COMPLETE', workspace=request['arguments']['workspace']))
        self.assertEqual(self.state['phase'], 'PHYSICAL_CHECKS')
        self.assertFalse(self.state['physical_checks_accepted'])
        with self.assertRaises(ValueError):
            guide.answer(self.state, 'checks', dict(preview=True))
        guide.answer(self.state, 'checks', dict(preview=True, capture_playback=True, original_looks=True))
        self.assertEqual(self.state['phase'], 'COMPLETE')

    def test_ended_worker_is_required_before_unplug_guidance(self):
        self.prepare()
        self.launch('install', confirmed=True, battery=90, replace_slots=True)
        with patch.object(guide, 'alive', return_value=True):
            self.finish(dict(phase='WAIT_RELOAD'), ended=False)
        self.assertEqual(self.state['phase'], 'RUNNING')
        self.assertNotIn('cold_reload_steps', guide.view(self.state))
        with patch.object(guide, 'alive', return_value=False):
            guide.poll(self.state)
        self.assertEqual(self.state['phase'], 'NEEDS_REVIEW')
        self.assertNotIn('cold_reload_steps', guide.view(self.state))

    def test_failed_write_cannot_be_replayed_or_reconfigured(self):
        self.prepare()
        self.launch('install', confirmed=True, battery=90, replace_slots=True)
        job = Path(self.state['active']['job'])
        self.finish({}, success=False)
        self.assertEqual(self.state['phase'], 'NEEDS_REVIEW')
        calls = self.spawn.call_count
        for action in ('install', 'restore', 'continue'):
            with self.assertRaises(ValueError):
                self.launch(action, confirmed=True, battery=90, replace_slots=True)
        with self.assertRaises(ValueError):
            guide.configure(self.state, {})
        self.assertEqual(calls, self.spawn.call_count)
        self.assertTrue((job / 'request.private.json').is_file())

    def test_changed_assets_require_a_new_plan_before_any_launch(self):
        self.prepare()
        Path(self.state['plan']['looks'][0]['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.launch('install', confirmed=True, battery=90, replace_slots=True)
        self.assertEqual(self.state['phase'], 'READY_INSTALL')
        self.assertEqual(self.spawn.call_count, 2)

    def test_partial_slots_and_optional_features_are_explicit(self):
        guide.configure(self.state, dict(looks=[dict(slot=4, profile='Astia')], extras=dict(sound=True)))
        self.assertEqual(self.state['plan']['replaces_slots'], [4])
        self.prepare()
        self.launch('install', confirmed=True, battery=90, replace_slots=True)
        request = guide.read(Path(self.state['active']['job']) / 'request.private.json')
        self.assertEqual([r['slot'] for r in request['arguments']['options']['looks']], [4])
        self.assertTrue(request['arguments']['options']['sound'])
        self.finish(dict(phase='COMPLETE'))
        with self.assertRaises(ValueError):
            guide.answer(self.state, 'checks', dict(preview=True, capture_playback=True, original_looks=True))
        guide.answer(self.state, 'checks', dict(preview=True, capture_playback=True, original_looks=True, sound=False))
        self.assertEqual(self.state['phase'], 'NEEDS_REVIEW')

    def test_factory_restore_is_separate_and_verification_does_not_write(self):
        self.prepare(modified='yes')
        self.assertEqual(self.state['phase'], 'READY_RESTORE')
        self.launch('restore', confirmed=True, battery=90, replace_slots=True)
        request = guide.read(Path(self.state['active']['job']) / 'request.private.json')
        self.assertEqual(request['action'], 'direct_factory_reset')
        self.finish(dict(phase='AWAITING_RELOAD', workspace=request['arguments']['workspace']))
        guide.answer(self.state, 'reboot', dict(confirmed=True))
        self.launch('continue')
        verification = guide.read(Path(self.state['active']['job']) / 'request.private.json')
        self.assertEqual(verification['action'], 'direct_verify')
        self.finish(dict(phase='LOADED', workspace=request['arguments']['workspace']))
        self.assertEqual(self.state['phase'], 'READY_INSTALL')

    def test_stability_failure_is_retryable_without_enabling_install(self):
        self.camera()
        guide.answer(self.state, 'connected', dict(confirmed=True))
        self.launch('drivers')
        self.finish({})
        self.launch('stability')
        self.finish({}, success=False)
        self.assertEqual(self.state['phase'], 'READY_STABILITY')
        with self.assertRaises(ValueError):
            self.launch('install', confirmed=True, battery=90, replace_slots=True)

    def test_busy_before_backend_launch_can_retry_but_unknown_cannot(self):
        self.prepare()
        self.launch('install', confirmed=True, battery=90, replace_slots=True)
        job = Path(self.state['active']['job'])
        write_json(job / 'execution.private.json', dict(phase='ENDED', worker_started=False, error='busy'))
        guide.poll(self.state)
        self.assertEqual(self.state['phase'], 'READY_INSTALL')

    def test_save_failure_after_launch_cannot_turn_a_write_into_a_retry(self):
        self.prepare()
        real_save = guide.save
        count = 0
        def fail_after_launch(state, path):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('disk full after child launch')
            real_save(state, path)
        with patch.object(guide, 'save', side_effect=fail_after_launch):
            with self.assertRaises(OSError):
                self.launch('install', confirmed=True, battery=90, replace_slots=True)
        self.assertEqual(self.state['phase'], 'RUNNING')
        self.assertEqual(guide.read(self.path)['phase'], 'RUNNING')
        with self.assertRaises(ValueError):
            self.launch('install', confirmed=True, battery=90, replace_slots=True)

    def test_history_blocks_new_operations_including_other_guide_sessions(self):
        old = self.root / 'app/ai-guide/old/guide.private.json'
        write_json(old, dict(phase='NEEDS_REVIEW'))
        self.camera()
        guide.answer(self.state, 'connected', dict(confirmed=True))
        self.assertEqual(self.state['phase'], 'EXISTING_TRANSACTION')
        self.assertEqual(self.state['existing_transactions'][0]['workspace'], str(old.parent))
        with self.assertRaises(ValueError):
            self.launch('drivers')
        self.spawn.assert_not_called()

    def test_history_rechecked_immediately_before_new_install(self):
        self.prepare()
        write_json(self.root / 'app/work/old/direct.private.json', dict(phase='NEEDS_REVIEW'))
        with self.assertRaises(ValueError):
            self.launch('install', confirmed=True, battery=90, replace_slots=True)
        self.assertEqual(self.state['phase'], 'EXISTING_TRANSACTION')

    def test_completed_setup_accounts_for_recorded_same_body_checkpoint(self):
        root = self.root / 'app/work/setup'
        old, final = root / 'resources', root / 'final'
        identity = dict(usb_serial_sha256='test-body')
        write_json(old / 'direct.private.json', dict(phase='RESOURCE_RELOAD_VERIFIED', mode='install_all', identity=identity))
        write_json(final / 'direct.private.json', dict(phase='LOADED', mode='install_all', identity=identity))
        write_json(root / 'setup.private.json', dict(phase='COMPLETE', install_workspace=str(final),
                                                     resume_resource_from=str(old),
                                                     verify_result=dict(phase='LOADED', workspace=str(final))))
        self.assertEqual(guide.history([root]), [])
        write_json(old / 'direct.private.json', dict(phase='RESOURCE_RELOAD_VERIFIED', mode='install_all',
                                                    identity=dict(usb_serial_sha256='other-body')))
        self.assertEqual(len(guide.history([root])), 1)

    def test_known_prewrite_failure_is_evidence_not_an_unknown_write(self):
        old = self.root / 'app/work/old/direct.private.json'
        write_json(old, dict(schema='a7c2-direct-job/1', phase='NEEDS_REVIEW', mode='install_all', failed_during='READING', journal=[]))
        before = old.read_bytes()
        self.assertEqual(guide.history([old.parent]), [])
        self.assertEqual(before, old.read_bytes())
        write_json(old, dict(phase='NEEDS_REVIEW', mode='install_all', failed_during='WRITING', journal=[]))
        self.assertEqual(len(guide.history([old.parent])), 1)

    def test_unknown_history_is_not_treated_as_unmodified(self):
        self.prepare(modified='unknown')
        self.assertEqual(self.state['phase'], 'HISTORY_QUESTION')
        with self.assertRaises(ValueError):
            self.launch('restore', confirmed=True, battery=90, replace_slots=True)
        guide.answer(self.state, 'history', dict(modified='no'))
        self.assertEqual(self.state['phase'], 'READY_INSTALL')

    def test_duplicate_launcher_cannot_overwrite_execution_evidence(self):
        self.prepare()
        self.launch('install', confirmed=True, battery=90, replace_slots=True)
        job = Path(self.state['active']['job'])
        (job / 'launcher.claim').write_text('already running')
        write_json(job / 'execution.private.json', dict(phase='RUNNING', worker_started=True))
        before = (job / 'execution.private.json').read_bytes()
        with patch.object(guide.subprocess, 'Popen') as launch:
            self.assertEqual(guide.worker(job / 'request.private.json', self.backend), 2)
        launch.assert_not_called()
        self.assertEqual(before, (job / 'execution.private.json').read_bytes())

    def test_worker_rejects_modified_request_before_backend_launch(self):
        self.prepare()
        self.launch('install', confirmed=True, battery=90, replace_slots=True)
        job = Path(self.state['active']['job'])
        request = guide.read(job / 'request.private.json')
        request['arguments']['power_confirmed'] = False
        write_json(job / 'request.private.json', request)
        with patch.object(guide.subprocess, 'Popen') as launch:
            self.assertEqual(guide.worker(job / 'request.private.json', self.backend), 2)
        launch.assert_not_called()
        self.assertFalse(guide.read(job / 'execution.private.json')['worker_started'])

    def test_packaged_worker_protocol_with_strictly_offline_reference_check(self):
        """Exercise the real EXE/launcher, using tiny synthetic host-only inputs."""
        backend = guide.ROOT.parent / 'A7C2Tools-Windows-x64/A7C2Tools/A7C2Tools.exe'
        if sys.platform != 'win32' or not backend.is_file():
            self.skipTest('Optional Windows package is not present')
        cache = self.root / 'synthetic-reference'
        cache.mkdir()
        values = {'appFw.so': b'\x7fELF' + bytes(14) + b'\xb7\x00',
                  'cpapp-b.bin': b'synthetic fixture', 'CX89700_ALLLANG.bin': b'synthetic fixture'}
        for name, raw in values.items():
            (cache / name).write_bytes(raw)
        write_json(cache / 'reference.json', dict(model_code=0x20030014, version='2.01',
                                                 sizes={n: len(v) for n, v in values.items()}))
        job = self.session / 'jobs/offline-protocol-check'
        job.mkdir(parents=True)
        request = job / 'request.private.json'
        write_json(request, dict(schema='a7c2-desktop-job/1', action='factory_prepare',
                                 arguments=dict(source=str(cache)), job_dir=str(job),
                                 guide_session=str(self.session), version='3.0.3'))
        write_json(job / 'status.private.json', dict(phase='QUEUED'))
        self.state.update(phase='RUNNING', backend=str(backend),
                          active=dict(job=str(job), action='factory_prepare',
                                      request_sha256=guide.digest(request.read_bytes())))
        guide.save(self.state, self.path)
        result = subprocess.run([sys.executable, str(guide.ROOT / 'ai_guide.py'), '_worker',
                                 '--request', str(request), '--backend', str(backend)],
                                capture_output=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(guide.read(job / 'execution.private.json')['phase'], 'ENDED')
        status = guide.read(job / 'status.private.json')
        self.assertEqual(status['phase'], 'SUCCEEDED', status)
        self.assertFalse(status['result']['camera_io'])
        for name, raw in values.items():
            self.assertEqual((cache / name).read_bytes(), raw)

    def test_diagnostics_excludes_private_paths_binaries_and_freeform_errors(self):
        self.state['error'] = 'PRIVATE_SERIAL and secret path'
        self.state['last_job'] = dict(status=dict(phase='FAILED', error='PRIVATE_SERIAL', error_type='ValueError'))
        output = self.root / 'diagnostics.zip'
        guide.diagnostics(self.state, output)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.namelist(), ['guide-summary.json'])
            raw = archive.read('guide-summary.json').decode()
            self.assertNotIn('PRIVATE_SERIAL', raw)
            self.assertNotIn(str(self.root), raw)


if __name__ == '__main__':
    unittest.main()
