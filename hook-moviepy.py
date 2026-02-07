from PyInstaller.utils.hooks import collect_all, copy_metadata

# Ensure moviepy package assets and metadata are bundled.
datas, binaries, hiddenimports = collect_all('moviepy')
datas += copy_metadata('moviepy')
