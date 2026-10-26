"""Build a clean, self-contained Windows skill ZIP; never interact with USB."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
NAME = 'a7c2-fuji-install'
SOURCE_FILES = ('SKILL.md', 'README.md', 'agents/openai.yaml', 'scripts/guide.py', 'scripts/guide.cmd')
FORBIDDEN_SUFFIXES = {'.arw', '.hif', '.jpg', '.jpeg', '.log', '.pyc', '.dat'}


def distributable(path):
    parts = {p.lower() for p in path.parts}
    return (not path.is_symlink() and '.private.' not in path.name.lower()
            and path.suffix.lower() not in FORBIDDEN_SUFFIXES
            and not parts.intersection({'__pycache__', '.git', 'log', 'logs', 'private', 'diagnostic-reports'})
            and not ('diagnostic' in path.name.lower() and path.suffix.lower() in {'.zip', '.json', '.txt'}))


def copy_public(source, target):
    source, target = Path(source), Path(target)
    if source.is_file():
        if not distributable(source):
            raise ValueError('Refusing private or unsupported input: ' + source.name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return
    copies = []
    for path in sorted(source.rglob('*')):
        if path.is_file() and distributable(path.relative_to(source)):
            if path.is_symlink():
                raise ValueError('Symbolic links are not package inputs')
            copies.append((path, target / path.relative_to(source)))
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(lambda pair: copy_public(*pair), copies))


def build(backend, output):
    if sys.platform != 'win32' or sys.maxsize <= 2 ** 32:
        raise ValueError('Build the Windows x64 skill on Windows x64 Python.')
    backend = Path(backend).resolve()
    for needed in ('A7C2Tools.exe', '_internal/python311.dll', 'Profiles/catalog.json', 'LICENSE'):
        if not (backend.parent / needed).is_file():
            raise ValueError('Incomplete backend package: ' + needed)
    identifier = uuid.uuid4().hex[:10]
    work = ROOT / 'build' / ('skill-' + identifier)
    work.mkdir(parents=True)
    package = work / NAME
    package.mkdir()
    for name in SOURCE_FILES:
        copy_public(ROOT / 'skills' / NAME / name, package / name)
    copy_public(ROOT / 'LICENSE', package / 'LICENSE')
    copy_public(ROOT / 'docs/en/notices.md', package / 'assets/notices.md')
    copy_public(ROOT / 'docs/zh-CN/notices.md', package / 'assets/notices.zh-CN.md')
    for relative in ('docs/licenses', 'src/fl23/licenses'):
        copy_public(ROOT / relative, package / 'assets/licenses' / Path(relative).name)
    copy_public(ROOT / 'src/desktopapp/vendor/fwtool-LICENSE.txt', package / 'assets/licenses/fwtool-LICENSE.txt')
    for dist_name in ('numpy', 'pyinstaller'):
        dist = metadata.distribution(dist_name)
        for item in dist.files or ():
            if 'license' in str(item).lower() or Path(item).name.upper().startswith('COPYING'):
                path = Path(dist.locate_file(item))
                if path.is_file():
                    copy_public(path, package / 'assets/licenses' / dist_name / Path(*Path(item).parts[1:]))
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        copy_public(python_license, package / 'assets/licenses/Python-LICENSE.txt')
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
               '--console', '--name', 'A7C2Guide', '--distpath', str(work / 'frozen'),
               '--workpath', str(work / 'pyinstaller'), '--specpath', str(work),
               '--paths', str(ROOT / 'src'), '--paths', str(ROOT / 'src/looks'),
               '--exclude-module', 'desktopapp.lookbatch', '--exclude-module', 'usb',
               '--exclude-module', 'PySide6', '--exclude-module', 'scipy',
               '--exclude-module', 'pytest', '--hidden-import', 'looktool.photobasis',
               '--hidden-import', 'looktool.rawidentity', '--hidden-import', 'looktool.devicelock',
               str(ROOT / 'ai_skill.py')]
    subprocess.run(command, cwd=ROOT, check=True)
    copy_public(work / 'frozen/A7C2Guide', package / 'assets/runtime/guide')
    # Allowlist only original distribution components. A used application's log,
    # diagnostics or private state at its top level never enter the archive.
    for relative in ('A7C2Tools.exe', '_internal', 'Profiles', 'LICENSE', 'README.md', 'README.zh-CN.md'):
        print('Copying backend component: ' + relative, flush=True)
        copy_public(backend.parent / relative, package / 'assets/runtime/backend' / relative)
    return archive_package(package, output)


def archive_package(package, output):
    """Audit and archive an already staged, clean distribution."""
    package = Path(package).resolve()
    manifest = dict(schema='a7c2-skill-package/1', platform='windows-x64',
                    repository='https://github.com/FlyMercurian/a7c2-fuji-ai-skill',
                    camera_io=False, files=[])
    if (package / 'assets/runtime/guide/_internal/preset-only.json').is_file():
        manifest['flavor'] = 'preset-only'
    members = []
    for directory, _, names in os.walk(package):
        members.extend(Path(directory) / name for name in names
                       if Path(directory) != package or name != 'package-manifest.json')
    members.sort()
    def inspect(path):
        relative = path.relative_to(package)
        if path.is_symlink() or not distributable(relative):
            raise ValueError('Unsafe package output: ' + str(relative))
        with path.open('rb') as stream:
            size = os.fstat(stream.fileno()).st_size
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        return dict(path=relative.as_posix(), size=size, sha256=checksum)
    with ThreadPoolExecutor(max_workers=8) as executor:
        manifest['files'] = list(executor.map(inspect, members))
    (package / 'package-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Refusing to replace an existing release ZIP: ' + str(output))
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=3) as archive:
        for path in [*members, package / 'package-manifest.json']:
            archive.write(path, NAME + '/' + path.relative_to(package).as_posix())
    with output.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    output.with_suffix(output.suffix + '.sha256').write_text(checksum + '  ' + output.name + '\n', encoding='ascii')
    print(json.dumps(dict(zip=str(output), unpacked=str(package), bytes=output.stat().st_size,
                          files=len(manifest['files']) + 1, sha256=checksum, camera_io=False), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', type=Path, required=True, help='A7C2Tools.exe from a complete Windows package')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.backend, args.output)
