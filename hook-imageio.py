from PyInstaller.utils.hooks import collect_all, copy_metadata

# imageio is queried through importlib.metadata by moviepy/imageio itself.
datas, binaries, hiddenimports = collect_all('imageio')
datas += copy_metadata('imageio')
