"""Check a PyInstaller build's modules and assets without launching the app."""

import sys
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader


def main() -> None:
    executable = Path(sys.argv[1])
    archive = CArchiveReader(str(executable))
    internal = executable.parent / '_internal'
    root = Path(__file__).resolve().parent.parent
    for name in ("widget.ps1", "config.example.json"):
        bundled = (internal / name).read_bytes() if internal.is_dir() else archive.extract(name)
        if bundled != (root / name).read_bytes():
            raise SystemExit(f"Bundled {name} does not match the current source")
    if "native_app" not in archive.toc:
        raise SystemExit("Native app entry point is missing")
    if (internal / 'PYZ.pyz').is_file():
        from PyInstaller.archive.readers import ZlibArchiveReader
        modules = ZlibArchiveReader(str(internal / 'PYZ.pyz')).toc
    else:
        modules = archive.open_embedded_archive("PYZ.pyz").toc
    if "collector" not in modules:
        raise SystemExit("Collector module is missing")
    print("Bundle OK: native host, collector, widget, and example configuration")


if __name__ == "__main__":
    main()
