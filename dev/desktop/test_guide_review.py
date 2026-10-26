"""Offline review never mistakes missing write evidence for permission to replay."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from desktopapp import guide
from desktopapp.paths import write_json


class GuideReviewTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        environment = patch.dict(os.environ, {'A7C2_DESKTOP_DATA': str(self.root / 'app')})
        environment.start()
        self.addCleanup(environment.stop)
        self.backend = self.root / 'A7C2Tools.exe'
        self.backend.write_bytes(b'not executable; test only')
        (self.root / '_internal').mkdir()
        look = self.root / 'fixture.a7look'
        look.write_bytes(b'look fixture')
        rows = [dict(slot=1, profile='Eterna', name='Eterna', path=str(look), sha256=guide.digest(look.read_bytes()))]
        assets = patch.object(guide, 'assets', return_value=(rows, []))
        assets.start()
        self.addCleanup(assets.stop)
        processes = patch('desktopapp.transactionevidence.running_camera_processes', return_value=[])
        processes.start()
        self.addCleanup(processes.stop)
        alive = patch.object(guide, 'alive', return_value=False)
        alive.start()
        self.addCleanup(alive.stop)
        guide.initialize(self.root / 'session', self.backend, self.root)
        self.state, self.path = guide.load(self.root / 'session')
        guide.answer(self.state, 'camera', dict(model='ILCE-7CM2', firmware='2.01', modified='no'))
        guide.answer(self.state, 'connected', dict(confirmed=True))
        self.spawn = Mock(return_value=Mock(pid=987654))

    def launch(self, operation='drivers'):
        self.state['phase'] = {'drivers': 'READY_DRIVERS', 'install': 'READY_INSTALL'}[operation]
        guide.start(self.state, self.path, operation,
                    dict(confirmed=True, battery=80, replace_slots=True), spawn=self.spawn)
        self.state['phase'] = 'NEEDS_REVIEW'
        guide.save(self.state, self.path)
        return Path(self.state['active']['job'])

    def test_queued_nonwriting_launch_can_be_reviewed_without_altering_original_evidence(self):
        job = self.launch()
        before = {p.name: p.read_bytes() for p in job.iterdir()}
        saved = self.path.read_bytes()
        plan = self.state['plan'].copy()
        report = guide.review(self.state)
        self.assertTrue(report['can_apply'])
        self.assertFalse(report['applied'])
        self.assertFalse(report['worker_never_started_proven'])
        self.assertEqual(saved, self.path.read_bytes())
        report = guide.review(self.state, apply=True)
        self.assertTrue(report['applied'])
        self.assertEqual(self.state['phase'], 'READY_DRIVERS')
        self.assertEqual(self.state['plan'], plan)
        self.assertEqual(before, {p.name: p.read_bytes() for p in job.iterdir()})
        self.assertEqual(self.spawn.call_count, 1)

    def test_missing_logs_never_release_an_unknown_install(self):
        self.launch('install')
        self.assertFalse(guide.review(self.state, apply=True)['can_apply'])
        self.assertEqual(self.state['phase'], 'NEEDS_REVIEW')

    def test_positive_ended_before_backend_receipt_restores_previous_install_step(self):
        job = self.launch('install')
        write_json(job / 'execution.private.json', dict(phase='ENDED', worker_started=False))
        result = guide.review(self.state, apply=True)
        self.assertTrue(result['worker_never_started_proven'])
        self.assertTrue(result['applied'])
        self.assertEqual(self.state['phase'], 'READY_INSTALL')

    def test_started_backend_without_end_receipt_stays_blocked(self):
        job = self.launch()
        write_json(job / 'execution.private.json', dict(phase='RUNNING', worker_started=True))
        self.assertFalse(guide.review(self.state, apply=True)['can_apply'])

    def test_request_mismatch_stays_blocked(self):
        job = self.launch()
        request = guide.read(job / 'request.private.json')
        request['action'] = 'setup_all'
        write_json(job / 'request.private.json', request)
        self.assertFalse(guide.review(self.state, apply=True)['can_apply'])

    def test_running_relevant_process_keeps_the_block(self):
        self.launch()
        with patch('desktopapp.transactionevidence.running_camera_processes', return_value=[dict(pid=123, name='A7C2Tools.exe')]):
            self.assertFalse(guide.review(self.state, apply=True)['can_apply'])

    def test_supervisor_claim_without_end_receipt_stays_blocked(self):
        job = self.launch()
        (job / 'launcher.claim').write_text('987654', encoding='ascii')
        self.assertFalse(guide.review(self.state, apply=True)['can_apply'])
