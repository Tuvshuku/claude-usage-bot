"""Check a PyInstaller build's modules and assets without launching the app."""

import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


def main() -> None:
    archive = CArchiveReader(sys.argv[1])
    root = Path(__file__).resolve().parent.parent
    for name in ("widget.ps1", "config.example.json"):
        if archive.extract(name) != (root / name).read_bytes():
            raise SystemExit(f"Bundled {name} does not match the current source")
    if "native_app" not in archive.toc:
        raise SystemExit("Native app entry point is missing")
    if "collector" not in archive.open_embedded_archive("PYZ.pyz").toc:
        raise SystemExit("Collector module is missing")
    print("Bundle OK: native host, collector, widget, and example configuration")


if __name__ == "__main__":
    main()
