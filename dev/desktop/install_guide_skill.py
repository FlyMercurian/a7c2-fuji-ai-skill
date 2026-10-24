"""Install the conversational skill; no USB access, drivers or camera writes."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'src'))
    from desktopapp.guide import assets, backend_path, DEFAULTS
    backend = backend_path(args.backend)
    assets(backend.parent / 'Profiles', [dict(slot=i, profile=n) for i, n in enumerate(DEFAULTS, 1)])
    codex_root = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    destination = args.destination or codex_root / 'skills' / 'a7c2-fuji-install'
    # Preserve a previous local session and configuration when updating this skill.
    settings = destination / 'settings.private.json'
    config = json.loads(settings.read_text(encoding='utf-8')) if settings.exists() else {}
    for path in (ROOT / 'skills/a7c2-fuji-install').rglob('*'):
        if path.is_file() and path.suffix != '.pyc' and path.name != 'settings.private.json':
            target = destination / path.relative_to(ROOT / 'skills/a7c2-fuji-install')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    config.update(project=str(ROOT), python=sys.executable, backend=str(backend))
    settings.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(installed=str(destination), camera_io=False), ensure_ascii=False))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
