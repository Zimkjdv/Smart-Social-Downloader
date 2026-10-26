"""Shared bootloader script; executable name selects the public default role."""
import multiprocessing
from pathlib import Path
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if not getattr(sys, "frozen", False):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ssdl.runtime_entry import main
    raise SystemExit(main(gui=Path(sys.executable).name.lower() == "smartsocialdownloader.exe"))
