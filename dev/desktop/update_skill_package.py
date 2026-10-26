"""Refresh only a standalone guide and instructions, retaining the base engine."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'a7c2-fuji-install/'


def update(base, guide_dist, output, patch_output):
    updates = {}
    for name in ('SKILL.md', 'README.md', 'agents/openai.yaml', 'scripts/guide.py', 'scripts/guide.cmd'):
        updates[name] = (ROOT / 'skills/a7c2-fuji-install' / name).read_bytes()
    for path in Path(guide_dist).rglob('*'):
        if path.is_file():
            updates['assets/runtime/guide/' + path.relative_to(guide_dist).as_posix()] = path.read_bytes()
    assert 'assets/runtime/guide/A7C2Guide.exe' in updates
    for path in (output, patch_output):
        if Path(path).exists():
            raise ValueError('Refusing to replace an existing release: ' + str(path))
    with zipfile.ZipFile(base) as original:
        manifest = json.loads(original.read(PREFIX + 'package-manifest.json'))
        old_rows = {r['path']: r for r in manifest['files']}
        rows = {name: row for name, row in old_rows.items() if not name.startswith('assets/runtime/guide/') and name not in updates}
        for name, data in updates.items():
            rows[name] = dict(path=name, size=len(data), sha256=hashlib.sha256(data).hexdigest())
        manifest['files'] = [rows[name] for name in sorted(rows)]
        manifest['guide_revision'] = '2026-10-26-r2-offline-review'
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=2).encode('utf-8')
        changed = {name: data for name, data in updates.items()
                   if old_rows.get(name, {}).get('sha256') != rows[name]['sha256']}
        with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=3) as target:
            for name in sorted(rows):
                if name in updates:
                    target.writestr(PREFIX + name, updates[name])
                else:
                    with original.open(PREFIX + name) as source, target.open(PREFIX + name, 'w') as dest:
                        shutil.copyfileobj(source, dest, length=1048576)
            target.writestr(PREFIX + 'package-manifest.json', manifest_bytes)
        with zipfile.ZipFile(patch_output, 'x', zipfile.ZIP_DEFLATED, compresslevel=3) as target:
            for name, data in sorted(changed.items()):
                target.writestr(PREFIX + name, data)
            target.writestr(PREFIX + 'package-manifest.json', manifest_bytes)
    for path in (Path(output), Path(patch_output)):
        with path.open('rb') as stream:
            checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
        path.with_suffix(path.suffix + '.sha256').write_text(checksum + '  ' + path.name + '\n', encoding='ascii')
    print(json.dumps(dict(full_zip=str(output), patch_zip=str(patch_output),
                          changed_files=list(changed), patch_bytes=Path(patch_output).stat().st_size,
                          camera_io=False), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--guide-dist', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--patch-output', type=Path, required=True)
    args = parser.parse_args()
    update(args.base, args.guide_dist, args.output, args.patch_output)
