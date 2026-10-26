"""Portable skill entry: bundled backend, per-user progress, no source checkout."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys

from . import guide
from .paths import data_root, write_json


def settings_path():
    from .presetpolicy import enabled
    return data_root() / ('ai-skill-presets/settings.private.json' if enabled() else 'ai-skill/settings.private.json')


def saved_settings():
    path = settings_path()
    if path.exists():
        return guide.read(path)
    # An in-place upgrade may keep an existing installation's session. Never
    # change its backend, assets or plan, or copy it into a distributable archive.
    from .presetpolicy import enabled
    if getattr(sys, 'frozen', False) and not enabled():
        legacy = Path(sys.executable).resolve().parents[3] / 'settings.private.json'
        if legacy.is_file():
            value = guide.read(legacy)
            return {'session': value['session']} if value.get('session') else {}
    return {}


def doctor():
    backend = guide.backend_path()
    catalog = guide.read(backend.parent / 'Profiles/catalog.json')
    for profile in catalog['profiles']:
        guide.assets(backend.parent / 'Profiles', [{'slot': 1, 'profile': profile['name']}])
    from .presetpolicy import enabled
    return dict(ok=True, camera_io=False, platform=sys.platform, preset_only=enabled(),
                supported_platform=sys.platform == 'win32', bundled_backend=str(backend),
                profiles=len(catalog['profiles']), source_checkout_required=False,
                python_install_required=False, settings=str(settings_path()))


def main(argv=None):
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if arguments in (['doctor'], ['doctor', '--native-check']):
            result = doctor()
            if arguments == ['doctor', '--native-check']:
                from .presetselftest import run
                result['native_check'] = run()
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if arguments != ['init']:
            return guide.main(arguments)
        # Serialize first invocation so simultaneous chats do not create two
        # independent sessions. Normal guide commands keep their existing locks.
        with guide.lock(settings_path().with_suffix('.lock')):
            config = saved_settings()
            if config.get('session'):
                return guide.main(['--session', config['session'], 'status'])
            output = io.StringIO()
            with redirect_stdout(output):
                code = guide.main(['init'])
            value = json.loads(output.getvalue())
            if code == 0:
                write_json(settings_path(), {'session': value['session']})
            print(json.dumps(value, ensure_ascii=False, indent=2))
            return code
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc), camera_io=False,
                              next_action='保留现有进度并检查文件；不要重新安装或重试结果未知的写入。'), ensure_ascii=False))
        return 2
