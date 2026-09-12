# LocalCrawler 3.1

把來源變成重點。A local-first research assistant for webpages and YouTube.

貼上連結，取得可核對的閱讀報告：單篇摘要、影片時間點，或多篇文章的共通點與差異。繁體中文桌面介面，Crawl4AI 擷取網頁，Ollama 整理內容，Whisper 在本機辨識語音。

## 為什麼使用

- **影片不用手動找字幕**：優先讀取公開字幕；未提供字幕時，嘗試下載公開音訊並在本機轉錄，顯示進度。
- **跨來源比較**：共通點與差異必須引用至少兩份文件；引用不符合條件時顯示比較失敗。引用檢查不保證 AI 判讀正確。
- **保留證據**：原文、時間點、摘要與來源對照分開保存。報告內連結可回到來源。
- **本機 AI**：不需要付費 API 金鑰。網路用於來源擷取及首次下載模型，AI 請求僅送往這台電腦的 Ollama。
- **桌面與 CLI 共用流程**：方便日常操作，也能接入自己的研究腳本。

## 開始使用（Windows / Python 3.12）

安裝包含 Tcl/Tk 的 Python 3.12，在專案資料夾開啟 PowerShell：

```powershell
.\setup.ps1
```

腳本建立專案專用 `.venv`、安裝依賴與 Chromium，不修改系統執行政策。若系統限制腳本，使用以下等效指令：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m playwright install chromium
```

要使用 AI，安裝並啟動 [Ollama](https://ollama.com/download/windows)，下載模型：

```powershell
ollama pull qwen2.5:7b
```

模型約 4.7 GB，首次載入需要時間。記憶體不足可改用 `qwen2.5:3b`，或選「基本摘錄」；小模型的整理品質較有限。Whisper small 約 0.5 GB，第一次處理無字幕影片會自動下載，之後使用本機快取。語音轉錄採 CPU int8，不需額外安裝 CUDA。

雙擊 **launch.cmd** 或 **啟動爬蟲.bat**。貼網址（每行一個），按「開始整理」。模型與爬取參數在「設定與模型」中。兩個以上來源成功後，使用「整批比較／比較來源」閱讀合併報告；歷史結果也可重新讀取比較報告。

## 命令列

```powershell
.\.venv\Scripts\python cli.py https://example.com --basic
.\.venv\Scripts\python cli.py URL1 URL2 --model qwen2.5:7b
.\.venv\Scripts\python doctor.py
```

CLI 結束碼：0 代表要求的單頁操作成功；1 代表有來源擷取或 AI 摘要失敗；2 代表輸入錯誤；130 代表中斷。整批比較的完成情況請另查看報告。

## 保存什麼

每次作業在 `downloads/日期時間_識別碼/` 建立資料夾：

| 檔案 | 內容 |
| --- | --- |
| `001_*.md` | 完整擷取原文 |
| `001_summary.md` / `001_sources.md` | 摘要和來源段落 |
| `batch_summary.md` / `batch_sources.md` | 多來源比較和引用內容 |
| `batch_comparison.json` | 成功的結構化 AI 比較 |
| `results.json` / `results.csv` | 個別來源結果與錯誤 |
| `run.json` | 已處理與未完成網址 |

原文在摘要前保存。停止後保留已保存結果，終止背景轉錄程序並清除該次暫存音訊。模型快取不會刪除。下載、設定、日誌與模型不包含在發布包中。

## 已知限制

這是研究輔助工具，AI 來源編號通過格式檢查不代表語意一定正確。語音辨識可能聽錯人名、產品名或數字；重要結論請點擊時間點核對。影片只處理語音或字幕，不理解畫面。

音訊限可公開取得、非直播、90 分鐘內且下載小於 120 MB 的影片。遇到登入、私密影片、平台封鎖、驗證碼或 robots.txt 禁止時會停止該來源，不使用 Cookie 或代理繞過限制。

單篇 AI 最多分析前約 36,000 字元；分段摘要保留在報告後方。比較會為各來源分配等額文字預算，並標示只比較選取內容。原文不會因此截短。每批最多 100 個網址；只擷取輸入頁面，不自動遍歷整站。Windows 已測試；其他系統的桌面啟動尚未驗證。

## 開發與授權

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

參考 [貢獻指南](CONTRIBUTING.md)、[架構與路線圖](docs/ROADMAP.md)、[測試說明](docs/TESTING.md)。GitHub Actions 設定會在 Windows 執行測試；本機準備發布包不代表已執行雲端 CI。

本專案程式碼採 MIT 授權。依賴套件、語音／語言模型與擷取內容仍遵循各自授權，不隨本專案重新授權。

使用的開源工具：[Crawl4AI](https://github.com/unclecode/crawl4ai)、[YouTube Transcript API](https://github.com/jdepoix/youtube-transcript-api)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[Ollama](https://github.com/ollama/ollama)。
