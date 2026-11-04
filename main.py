"""Entry point: `python main.py` opens the GUI, `python main.py devices` runs the CLI."""
import sys

if len(sys.argv) > 1:
    from adb_studio.cli import main
    raise SystemExit(main())
from adb_studio.app import main
main()
