# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spec für StoneBook V3 (onedir, windowed)."""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

spec_dir = Path(SPECPATH)
app_dir = spec_dir.parent          # ...\StoneBook\app
pkg_dir = app_dir / "stonebook"

datas = [
    (str(pkg_dir / "db" / "schema.sql"), "stonebook/db"),
    (str(pkg_dir / "migration" / "duplikat_gruppen.json"), "stonebook/migration"),
    (str(pkg_dir / "resources" / "StoneBoock_Object_Template_v4_2.docx"), "stonebook/resources"),
]

hiddenimports = collect_submodules("anthropic") + ["keyring.backends.Windows"]

a = Analysis(
    [str(pkg_dir / "__main__.py")],
    pathex=[str(app_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "matplotlib", "numpy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="StoneBook",
    console=False,
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="StoneBook")
