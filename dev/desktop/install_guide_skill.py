"""Install an extracted standalone skill package without camera interaction."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True, help='Extracted a7c2-fuji-install folder')
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    package = args.package.resolve()
    slim = (package / 'assets/runtime/guide/_internal/preset-only.json').is_file()
    required = ['SKILL.md', 'scripts/guide.cmd', 'assets/runtime/guide/A7C2Guide.exe', 'package-manifest.json']
    required += (['assets/runtime/guide/Profiles/catalog.json'] if slim else
                 ['assets/runtime/backend/A7C2Tools.exe', 'assets/runtime/backend/Profiles/catalog.json'])
    for relative in required:
        if not (package / relative).is_file():
            parser.error('Incomplete standalone package: ' + relative)
    codex_root = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    destination = (args.destination or codex_root / 'skills' / 'a7c2-fuji-install').resolve()
    if destination == package or package in destination.parents or destination in package.parents:
        parser.error('Package and destination must be separate directories.')
    if slim and (destination / 'assets/runtime/backend').exists():
        parser.error('Extract the preset-only package into a fresh directory; retain the old runtime for its transactions.')
    # The manifest is the allowlist: user settings, sessions and logs are never
    # installed, shared or removed. An existing local legacy session is retained.
    manifest = json.loads((package / 'package-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'a7c2-skill-package/1':
        parser.error('Unsupported package manifest.')
    import hashlib
    paths = [row['path'] for row in manifest['files']] + ['package-manifest.json']
    for row in manifest['files']:
        relative = Path(row['path'])
        if relative.is_absolute() or relative.drive or '..' in relative.parts:
            parser.error('Package member must use a relative path without traversal.')
        source = (package / relative).resolve()
        target = (destination / relative).resolve()
        if destination not in target.parents:
            parser.error('Package target is outside the destination.')
        if package not in source.parents or '.private.' in source.name or not source.is_file():
            parser.error('Unsafe or missing package member.')
        with source.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                parser.error('Package checksum mismatch: ' + row['path'])
    for relative in paths:
        path = package / relative
        target = destination / relative
        if path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file() and path.read_bytes() == target.read_bytes():
                continue
            shutil.copy2(path, target)
    print(json.dumps(dict(installed=str(destination), camera_io=False), ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
