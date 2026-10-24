"""Locate the installed project and invoke its JSON guide with its own Python."""
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    config_path = Path(__file__).resolve().parents[1] / 'settings.private.json'
    try:
        config = json.loads(config_path.read_text(encoding='utf-8')) if config_path.exists() else {}
        repo = Path(config.get('project', Path(__file__).resolve().parents[3]))
        runner = Path(config.get('python', repo / '.venv-desktop' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')))
        entry = repo / 'ai_guide.py'
        if not runner.is_file() or not entry.is_file():
            raise ValueError('本地向导环境缺失，请重新运行项目 dev/desktop/install_guide_skill.py 配置技能。')
        arguments = sys.argv[1:]
        # Re-invocation resumes the same session; never silently starts over.
        if arguments == ['init'] and config.get('session'):
            arguments = ['--session', config['session'], 'status']
        elif arguments == ['init'] and config.get('backend'):
            arguments += ['--backend', config['backend']]
        result = subprocess.run([str(runner), str(entry), *arguments], capture_output=True, encoding='utf-8',
                                env=dict(os.environ, PYTHONIOENCODING='utf-8'))
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
        if result.returncode == 0 and 'init' in arguments:
            value = json.loads(result.stdout)
            config.update(project=str(repo), python=str(runner), session=value['session'])
            config_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = config_path.with_suffix('.new')
            temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
            temporary.replace(config_path)
        return result.returncode
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps(dict(ok=False, error=str(exc)), ensure_ascii=False))
        return 2


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
