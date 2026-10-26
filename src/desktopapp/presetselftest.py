"""Exercise the slim package's real compiler and imports without any USB access."""
from pathlib import Path
import sys
import tempfile


def run():
    from .presetpolicy import enabled
    if not enabled():
        raise ValueError('此自检仅用于预制滤镜精简包。')
    import usb.core
    original = usb.core.find
    def forbidden(*args, **kwargs):
        raise AssertionError('Offline self-test must not enumerate a physical camera')
    usb.core.find = forbidden
    try:
        from .worker import setup_runtime, run as dispatch
        setup_runtime()
        from looktool import checkpointworker, nativebuild, runtimebindings
        from looktool.devicesession import modules
        transport, core = modules()
        core.assets()
        from Cryptodome.Hash import SHA256
        assert len(SHA256.new(b'preset-only-offline').digest()) == 32
        from looktool import photoio, device_layout
        photoio.template()
        device_layout.runtime()
        # Exercise a shared settings path whose optional desktop imports must
        # remain available even though preset plans never enable those features.
        from collections import namedtuple
        from types import SimpleNamespace
        from looktool import direct, bundle
        prop = namedtuple('Property', 'data attr')
        key = 0x02cf0cd0
        records = [{key: prop(b'\x01', 0)}, {}]
        camera = SimpleNamespace(records=lambda raw: records)
        with tempfile.TemporaryDirectory(prefix='preset-native-offline-') as temporary:
            root = Path(temporary)
            prepared = direct.DirectJob(root / 'settings').settings(camera,
                        {'settings-ram.bin': b'RAM', 'settings-saved.bin': b'SAVED'}, [{key: b'\0'}, {}])
            assert prepared[1][0][key].data == b'\0' and prepared[3][0][key].data == b'\x01'
            assert bundle.plan({'appFw.so': b'AP', 'cpapp-b.bin': b'CP'}, [{}, {}],
                               dict(fl23=False, sound=False, _preset_only=True), [])[1] == [{}, {}]
            before = {'appFw.so': bytes(8192), 'cpapp-b.bin': bytes(8192)}
            after = dict(before, **{'cpapp-b.bin': b'\x01' + bytes(8191)})
            programs = checkpointworker.build_programs(before, after, root / 'program')
            purge = checkpointworker.build_purge(root / 'names', '1234567890abcdef')
            header = root / 'names/names.private.h'
            text = header.read_text(encoding='ascii').replace('#define NAMES_PURGE 1',
                    '#define NAMES_SKIP_AP 1\n#define BYTE_NAME_UPDATES 1\n#define BYTE_NAME_STREAM_INSTALL 1')
            header.write_text(text, encoding='ascii')
            nativebuild.compile_worker(nativebuild.ROOT / 'src/looks/native/names.c', header,
                                       root / 'names/forward.so', fingerprints=False)
            size = max(at + len(bytes.fromhex(code)) for at, code in runtimebindings.SIGNATURES.items())
            ap = bytearray(size)
            for at, code in runtimebindings.SIGNATURES.items():
                ap[at:at + len(bytes.fromhex(code))] = bytes.fromhex(code)
            runtimebindings.build(bytes(ap), [dict(index=10, value=0)], root / 'bindings')
            for action in ('compile_look', 'sound_on', 'vertical_enable', 'plugin_install', 'direct_factory_reset'):
                try:
                    dispatch(action, {}, root)
                except ValueError as exc:
                    assert '精简包不支持' in str(exc)
                else:
                    raise AssertionError('Disabled action was accepted: ' + action)
        heavy = {'numpy', 'scipy', 'PySide6', 'unicorn', 'PIL', 'imageio_ffmpeg'}
        assert not any(name.split('.')[0] in heavy for name in sys.modules)
        return dict(camera_io=False, program_worker=True, forward_names_worker=True,
                    purge_names_worker=True, runtime_binding_worker=True,
                    native_workers_compiled=len(programs) + 3, optional_actions_rejected=True,
                    shared_settings_path=True, no_fitting_gui_audio_emulator_imports=True)
    finally:
        usb.core.find = original
