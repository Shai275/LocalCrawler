param(
    [string]$Python = ".venv\Scripts\python.exe",
    [string]$Output = "dist"
)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath $Python)) { throw "找不到打包用 Python：$Python" }
& $Python -c "import PyInstaller, crawl4ai, tkinter; print('Build environment ready')"
if ($LASTEXITCODE -ne 0) { throw "打包環境不完整。" }
& $Python -m PyInstaller --noconfirm --clean --distpath $Output --workpath build LocalCrawler.spec
if ($LASTEXITCODE -ne 0) { throw "EXE 打包失敗。" }
$release = Join-Path $Output "LocalCrawler"
# Frame extraction uses PyAV; OpenCV's two bundled video-I/O FFmpeg copies are unused.
Get-ChildItem (Join-Path $release "_internal\cv2") -Filter "opencv_videoio_ffmpeg*_64.dll" -ErrorAction SilentlyContinue |
    Remove-Item -Force
# Crawl4AI supports an optional undetected-browser backend, but LocalCrawler uses
# standard Playwright. Its hook can still copy the optional package as data.
$unusedPatchright = Join-Path $release "_internal\patchright"
if (Test-Path -LiteralPath $unusedPatchright) {
    Remove-Item -LiteralPath $unusedPatchright -Recurse -Force
}
# Headless Chromium ships language and grammatical-gender packs for every locale.
# The desktop UI supports English and Chinese, so retain those packs only.
$locales = Join-Path $release "_internal\browser\chromium_headless_shell-1234\chrome-headless-shell-win64\locales"
if (Test-Path -LiteralPath $locales) {
    Get-ChildItem -LiteralPath $locales -File | Where-Object {
        $_.Name -notmatch '^(en-US|zh-CN|zh-TW)(_|\.)'
    } | Remove-Item -Force
}
Copy-Item README.md, CHANGELOG.md, LICENSE -Destination $release -Force
@'
LocalCrawler 3.4 Windows 資料夾版

1. 雙擊 LocalCrawler.exe。
2. 設定、日誌與研究成果保存在 %LOCALAPPDATA%\LocalCrawler。
3. LocalCrawlerWorker.exe 與 _internal 是必要元件，請勿單獨刪除。
4. 更新時可替換整個程式資料夾，不會刪除使用者資料。
'@ | Set-Content (Join-Path $release "START_HERE.txt") -Encoding UTF8
$hashes = Get-ChildItem $release -File -Recurse | Get-FileHash -Algorithm SHA256
$hashes | ForEach-Object { "$($_.Hash.ToLower()) *$($_.Path.Substring($release.Length + 1).Replace('\','/'))" } |
    Set-Content (Join-Path $release "SHA256SUMS.txt") -Encoding ascii
Write-Host "完成：$release"
