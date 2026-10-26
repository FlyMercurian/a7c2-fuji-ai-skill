"""Build the offline, single-runtime Windows preset-only skill distribution."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
import uuid

from build_skill import ROOT, NAME, SOURCE_FILES, copy_public, archive_package

DESKTOP = ('__init__ paths guide reloadguide skillentry transactionevidence worker jobs allinone '
           'lookbatch presets completion usbcheck reviewnames presetpolicy presetselftest').split()
LOOKS = ('__init__ backupstore bundle checkpoint checkpointjob checkpointworker device_layout '
         'devicelock devicesession devicesettings direct directresume firmware hooks jobdiagnostics '
         'lookfile mlutformat namespause nameworker nativebuild photobasis photobuild photoformat '
         'photoio power rawidentity rawprofiles resources runtimebindings settingsresume '
         'six tablecodec usbidentity usbservice verticalpersist worker').split()
EXCLUDED = ('numpy scipy PySide6 PIL unicorn imageio_ffmpeg tkinter matplotlib pandas pytest '
            'desktopapp.window desktopapp.lookeditor desktopapp.plugins desktopapp.exiftool '
            'desktopapp.official desktopapp.recovery desktopapp.actions.sound '
            'desktopapp.actions.sound_state desktopapp.actions.look_compiler '
            'looktool.native looktool.color looktool.calibration looktool.nativefit '
            'looktool.coupledfit looktool.measuredfit looktool.measuredmodel looktool.compilelook '
            'looktool.devicecli looktool.devicejob looktool.portraitjob '
            'looktool.factoryrecover looktool.standalone looktool.rawauto looktool.rawimportcli '
            'looktool.renderbridge looktool.virtualraw looktool.bootstrap6 looktool.photolab '
            'looktool.photojoint looktool.photomeasure looktool.photocases looktool.sixbuild').split()


def profiles(source, destination):
    source, destination = Path(source), Path(destination)
    catalog = json.loads((source / 'catalog.json').read_text(encoding='utf-8'))
    assert len(catalog['profiles']) == 15
    for row in catalog['profiles']:
        original = json.loads((source / row['a7look']).read_text(encoding='utf-8'))
        slim = {k: v for k, v in original.items() if k not in {'raw_profile', 'source_reference'}}
        assert slim['table_base64'] == original['table_base64']
        assert slim['native_photo'] == original['native_photo']
        target = destination / row['a7look']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(slim, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        row.pop('dcp', None)
    (destination / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')


def build(source_profiles, output):
    work = ROOT / 'build' / ('preset-skill-' + uuid.uuid4().hex[:10])
    work.mkdir(parents=True)
    data = work / 'runtime-data'
    # Runtime source paths are meaningful to device/source and native worker checks.
    for name in DESKTOP:
        copy_public(ROOT / ('src/desktopapp/' + name + '.py'), data / ('src/desktopapp/' + name + '.py'))
    for name in ('__init__', 'usb_drivers', 'windows_pnp', 'macos_media', 'macos_authorization'):
        copy_public(ROOT / ('src/desktopapp/platforms/' + name + '.py'), data / ('src/desktopapp/platforms/' + name + '.py'))
    for name in ('__init__', 'catalog'):
        copy_public(ROOT / ('src/desktopapp/actions/' + name + '.py'), data / ('src/desktopapp/actions/' + name + '.py'))
    for name in LOOKS:
        copy_public(ROOT / ('src/looks/looktool/' + name + '.py'), data / ('src/looks/looktool/' + name + '.py'))
    for name in ('core.py', 'transport.py', 'assets', 'vendor'):
        copy_public(ROOT / 'src/camera_runtime' / name, data / 'src/camera_runtime' / name)
    for name in ('src/fl23/native', 'src/looks/native', 'src/looks/assets'):
        copy_public(ROOT / name, data / name)
    for name in ('wdi-simple.exe', 'COPYING.txt', 'SOURCE.txt'):
        copy_public(ROOT / 'desktop-assets/windows' / name, data / 'desktop-assets/windows' / name)
    (data / 'preset-only.json').write_text(json.dumps({'schema': 'a7c2-preset-only/1'}), encoding='utf-8')
    zig = ROOT / '.venv-desktop/Lib/site-packages/ziglang'
    for name in ('__init__.py', 'LICENSE', 'zig.exe', 'lib/std', 'lib/compiler_rt', 'lib/include',
                 'lib/std/std.zig', 'lib/zig.h', 'lib/compiler_rt.zig', 'lib/c.zig'):
        copy_public(zig / name, data / 'ziglang' / name)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
               '--name', 'A7C2Guide', '--distpath', str(work / 'frozen'), '--workpath', str(work / 'pyinstaller'),
               '--specpath', str(work), '--add-data', str(data) + ';.',
               '--paths', str(ROOT / 'src'), '--paths', str(ROOT / 'src/looks'),
               '--paths', str(ROOT / 'src/camera_runtime'), '--paths', str(ROOT / 'src/camera_runtime/vendor')]
    for name in EXCLUDED:
        command += ['--exclude-module', name]
    for name in ('usb', 'libusb_package', 'Cryptodome', 'elftools', 'keystone', 'capstone'):
        command += ['--collect-all', name]
    for name in ('transport', 'core', 'pmca.backup', 'pmca.usb.sony', 'pmca.usb.driver.generic.libusb',
                 'desktopapp.platforms.windows_pnp', 'desktopapp.platforms.macos_authorization',
                 'looktool.directresume', 'looktool.settingsresume', 'looktool.runtimebindings'):
        command += ['--hidden-import', name]
    command += [str(ROOT / 'ai_skill.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    package = work / NAME
    for name in SOURCE_FILES:
        copy_public(ROOT / 'skills' / NAME / name, package / name)
    copy_public(work / 'frozen/A7C2Guide', package / 'assets/runtime/guide')
    profiles(source_profiles, package / 'assets/runtime/guide/Profiles')
    for source, target in [('LICENSE', 'LICENSE'), ('docs/en/notices.md', 'assets/notices.md'),
                           ('docs/zh-CN/notices.md', 'assets/notices.zh-CN.md'),
                           ('docs/licenses', 'assets/licenses'), ('src/fl23/licenses', 'assets/licenses/fl23'),
                           ('src/desktopapp/vendor/fwtool-LICENSE.txt', 'assets/licenses/fwtool-LICENSE.txt')]:
        copy_public(ROOT / source, package / target)
    for dist_name in ('pyinstaller', 'pyusb', 'libusb-package', 'pycryptodomex', 'pyelftools', 'keystone-engine', 'capstone'):
        dist = metadata.distribution(dist_name)
        for item in dist.files or ():
            if 'license' in str(item).lower() or Path(item).name.upper().startswith('COPYING'):
                path = Path(dist.locate_file(item))
                if path.is_file():
                    copy_public(path, package / 'assets/licenses' / dist_name / Path(*Path(item).parts[1:]))
    copy_public(Path(sys.base_prefix) / 'LICENSE.txt', package / 'assets/licenses/Python-LICENSE.txt')
    print('Staged preset-only package: ' + str(package), flush=True)
    archive_package(package, output)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profiles', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.profiles, args.output)
