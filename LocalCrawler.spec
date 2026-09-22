# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH)
browser_root = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
datas = []
binaries = []
hiddenimports = collect_submodules("keyring.backends")

for package in ("crawl4ai", "playwright", "opencc", "rapidocr", "onnxruntime", "faster_whisper", "ctranslate2"):
    package_datas, package_binaries, package_hidden = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_hidden

for folder in ("chromium_headless_shell-1234", "ffmpeg-1011"):
    source = browser_root / folder
    if not source.is_dir():
        raise SystemExit(f"Missing Playwright runtime: {source}")
    datas.append((str(source), "browser/" + folder))

def common():
    # Analysis mutates collection inputs, so each executable receives its own lists.
    return dict(
        pathex=[str(root)], binaries=list(binaries), datas=list(datas), hiddenimports=list(hiddenimports),
        hookspath=[], hooksconfig={}, runtime_hooks=[],
        excludes=["pytest", "matplotlib", "IPython", "patchright", "scipy", "nltk"],
        noarchive=False, optimize=0,
    )

app_analysis = Analysis([str(root / "app.py")], **common())
app_pyz = PYZ(app_analysis.pure)
app_exe = EXE(
    app_pyz, app_analysis.scripts, [], exclude_binaries=True,
    name="LocalCrawler", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=False, disable_windowed_traceback=False,
)

worker_analysis = Analysis([str(root / "video_worker.py")], **common())
worker_pyz = PYZ(worker_analysis.pure)
worker_exe = EXE(
    worker_pyz, worker_analysis.scripts, [], exclude_binaries=True,
    name="LocalCrawlerWorker", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, console=True,
)

coll = COLLECT(
    app_exe, worker_exe,
    app_analysis.binaries, app_analysis.datas,
    worker_analysis.binaries, worker_analysis.datas,
    strip=False, upx=True, name="LocalCrawler",
)
