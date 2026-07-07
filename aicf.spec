# aicf.spec — PyInstaller one-dir build for AI Content Factory.
# Build with: pyinstaller aicf.spec
# Per-platform installers (NSIS / dmgbuild / AppImage) wrap this output.
from pathlib import Path
import sys

block_cipher = None
ROOT = Path(SPECPATH).resolve()

a = Analysis(
    ['main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        # Ship config defaults, prompts, schemas, theme QSS, caption/thumb templates.
        ('config', 'config'),
        ('gui/theme/dark.qss', 'gui/theme'),
        ('README.md', '.'),
    ],
    hiddenimports=[
        # faster-whisper lazy deps
        'faster_whisper',
        'ctranslate2',
        # PIL plugins
        'PIL._tkinter_finder',
        # google
        'googleapiclient.discovery_cache',
        'googleapiclient.discovery_cache.app_cache_memcache',
        'googleapiclient.discovery_cache.file_cache',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'pytest_qt', 'matplotlib'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='AI Content Factory',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(ROOT / 'assets' / 'icon.ico') if (ROOT / 'assets' / 'icon.ico').exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='AIContentFactory',
)
