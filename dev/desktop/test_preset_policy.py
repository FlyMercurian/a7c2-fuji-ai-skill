"""Preset-only scope is enforced before dispatch, not just hidden in prompts."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from desktopapp import presetpolicy, worker, guide
from looktool import native, tablecodec, bundle


class PresetPolicyTests(unittest.TestCase):
    def test_pure_codec_matches_original_validation_for_all_signed_byte_values(self):
        for value in range(256):
            raw = bytes([value]) * 1215
            if value < 64 or value >= 192:
                native.decode(raw)
                tablecodec.validate(raw)
            else:
                with self.assertRaises(ValueError): native.decode(raw)
                with self.assertRaises(ValueError): tablecodec.validate(raw)
        for raw in (b'', bytes(1214), bytes(1216)):
            with self.assertRaises(ValueError): tablecodec.validate(raw)

    def test_disabled_actions_are_rejected_before_power_checks_or_usb(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(presetpolicy, 'enabled', return_value=True):
            for action in ('compile_look', 'sound_on', 'vertical_enable', 'plugin_install', 'direct_factory_reset'):
                with self.assertRaisesRegex(ValueError, '精简包不支持'):
                    worker.run(action, {}, Path(temporary))

    def test_extra_features_cannot_be_enabled_in_a_preset_plan(self):
        for feature in presetpolicy.DISABLED:
            with self.assertRaises(ValueError):
                presetpolicy.options(dict(looks=[dict(slot=1)], **{feature: True}))
        result = presetpolicy.options(dict(looks=[dict(slot=1)]))
        self.assertTrue(result['_preset_only'])
        self.assertTrue(all(result[k] is False for k in presetpolicy.DISABLED))

    def test_preset_bundle_does_not_import_or_modify_sound(self):
        values = dict(fl23=False, sound=False, vertical_persistent=False, _preset_only=True)
        with patch.object(bundle.importlib.util, 'spec_from_file_location', side_effect=AssertionError('No sound module')):
            target, wanted, names = bundle.plan({'appFw.so': b'AP', 'cpapp-b.bin': b'CP'}, [{}, {}], values, [])
        self.assertEqual(target, {'appFw.so': b'AP', 'cpapp-b.bin': b'CP'})
        self.assertEqual(wanted, [{}, {}])
        self.assertIsNone(names)

    def test_preset_history_feedback_does_not_schedule_a_full_factory_reset(self):
        state = dict(phase='HISTORY_QUESTION', camera_confirmation={}, preset_only=True, events=[])
        guide.answer(state, 'history', dict(modified='yes'))
        self.assertEqual(state['phase'], 'READY_INSTALL')

    def test_stripped_library_preserves_all_camera_payloads_and_attribution(self):
        from build_preset_skill import profiles
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, output = root / 'source', root / 'output'
            source.mkdir()
            catalog = dict(profiles=[])
            for index in range(15):
                name = str(index) + '.a7look'
                document = dict(table_base64='camera-table', native_photo={'all-stages': index},
                                attribution='Preserve authors', raw_profile={'dcp_base64': 'omitted'},
                                source_reference={'cube_base64': 'omitted'})
                (source / name).write_text(json.dumps(document), encoding='utf-8')
                catalog['profiles'].append(dict(a7look=name, dcp='unneeded.dcp'))
            (source / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
            profiles(source, output)
            for path in output.glob('*.a7look'):
                original = json.loads((source / path.name).read_text())
                expected = {k: v for k, v in original.items() if k not in ('raw_profile', 'source_reference')}
                self.assertEqual(json.loads(path.read_text()), expected)
            self.assertFalse(list(output.rglob('*.dcp')))

    def test_custom_payload_and_seventh_slot_rejected_before_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            library = root / 'Profiles'
            library.mkdir()
            (library / 'preset.a7look').write_bytes(b'bundled')
            (library / 'catalog.json').write_text(json.dumps(dict(profiles=[dict(a7look='preset.a7look')])))
            custom = root / 'custom.a7look'
            custom.write_bytes(b'other')
            with patch('sys.executable', str(root / 'A7C2Guide.exe')):
                presetpolicy.selected_presets(dict(looks=[dict(slot=1, path=str(library / 'preset.a7look'))]))
                for row in [dict(slot=1, path=str(custom)), dict(slot=7, path=str(library / 'preset.a7look'))]:
                    with self.assertRaises(ValueError): presetpolicy.selected_presets(dict(looks=[row]))
