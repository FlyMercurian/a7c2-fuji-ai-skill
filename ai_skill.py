"""Build entry for the portable, self-contained Windows skill executable."""
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent / 'src'),
               str(Path(__file__).resolve().parent / 'src/looks')]

if __name__ == '__main__':
    sys.dont_write_bytecode = True
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    if getattr(sys, 'frozen', False):
        bundled = Path(sys._MEIPASS)
        if (bundled / 'preset-only.json').is_file():
            sys.path[:0] = [str(bundled / 'src'), str(bundled / 'src/looks'),
                           str(bundled / 'src/camera_runtime'), str(bundled / 'src/camera_runtime/vendor')]
    if len(sys.argv) >= 3 and sys.argv[1] == '--worker':
        from desktopapp.presetpolicy import enabled
        if not enabled():
            raise SystemExit('This entry does not provide a camera worker.')
        from desktopapp.worker import execute_request
        raise SystemExit(execute_request(Path(sys.argv[2])))
    else:
        from desktopapp.skillentry import main
        raise SystemExit(main())
