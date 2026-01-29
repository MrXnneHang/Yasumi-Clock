# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, copy_metadata
import os

packages_to_collect = ['imageio', 'moviepy', 'imageio_ffmpeg', 'pydub']
collected_datas = []
collected_binaries = []
collected_hiddenimports = ['audioop']

for package in packages_to_collect:
    t_datas, t_binaries, t_hidden = collect_all(package)
    collected_datas += t_datas
    collected_binaries += t_binaries
    collected_hiddenimports += t_hidden
    collected_datas += copy_metadata(package)

my_project_files = [
    ('yasumi_config.yml', '.'),  # 将根目录的 yml 打包到运行目录的根目录
    ('src.yml', '.'), 
    ('src', 'src')
]
collected_datas += my_project_files

a = Analysis(
    ['yasumi_clock.py'],
    pathex=[],
    binaries=collected_binaries,
    datas=collected_datas,
    hiddenimports=collected_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    [],
    exclude_binaries=True,
    name='yasumi_clock',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='yasumi_clock'
)

app_version = os.environ.get('APP_VERSION', '0.0.0')

app = BUNDLE(
    coll,
    name='YasumiClock.app',
    icon='src/img/icon.icns',
    version=app_version,
    bundle_identifier=f'person.yasumi_clock_{app_version}',
    info_plist={
        'CFBundleShortVersionString': app_version,
        'CFBundleVersion': app_version,
        'NSHighResolutionCapable': 'True'
    },
)