from PyInstaller.utils.hooks import collect_all, copy_metadata

# Collect package data/binaries/hidden imports required by imageio-ffmpeg.
datas, binaries, hiddenimports = collect_all('imageio_ffmpeg')

# Keep distribution metadata so importlib.metadata lookups work in one-file builds.
# Some environments use the PyPI distribution name `imageio-ffmpeg`.
for dist_name in ('imageio_ffmpeg', 'imageio-ffmpeg'):
    try:
        datas += copy_metadata(dist_name)
    except Exception:
        pass
