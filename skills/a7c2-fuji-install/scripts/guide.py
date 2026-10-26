"""Optional standard-library launcher for the bundled Windows guide."""
import json
from pathlib import Path
import subprocess
import sys


def main():
    executable = Path(__file__).resolve().parents[1] / 'assets/runtime/guide/A7C2Guide.exe'
    if sys.platform != 'win32' or not executable.is_file():
        print(json.dumps(dict(ok=False, error='请在 Windows x64 上使用完整解压的技能包（含 assets/runtime），不要只复制 SKILL.md。',
                              camera_io=False), ensure_ascii=False))
        return 2
    return subprocess.run([str(executable), *sys.argv[1:]]).returncode


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
