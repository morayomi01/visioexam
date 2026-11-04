# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build for the Windows release."""

from pathlib import Path
import sys

ROOT = Path(SPECPATH).resolve()
VENDOR_ROOT = ROOT / "vendor"
sys.path.insert(0, str(VENDOR_ROOT))

# YarnGPT opens its package's speaker prompts by filename using __file__, so
# keep its small helper package as real files alongside the executable bundle.
yarngpt_root = VENDOR_ROOT / "yarngpt"
yarngpt_data = [
    (str(path), str(Path("vendor") / "yarngpt" / path.parent.relative_to(yarngpt_root)))
    for path in yarngpt_root.rglob("*")
    if path.is_file() and path.suffix in {".py", ".json"}
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT), str(VENDOR_ROOT)],
    binaries=[],
    datas=yarngpt_data,
    hiddenimports=["sqlcipher3", "sqlcipher3.dbapi2", "sounddevice"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # The package is present as real data files; excluding its modules makes
    # Python load those files normally and preserves the helper's __file__ paths.
    excludes=["yarngpt"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="VisioExam",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="VisioExam",
)
