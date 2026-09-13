# LocalCrawler 3.2 — AI 供應商預覽版

本版加入 Ollama、OpenAI API、Gemini API 三種摘要後端，單頁、影片字幕與多來源比較共用來源驗證流程。26 項本機測試通過，並已實測 Ollama 摘要及 Windows 認證管理員。雲端後端目前通過模擬 API 測試，尚待使用者自己的金鑰進行真實 API 驗證。

影片摘要更新：使用影片專用的「影片大綱／值得記住的重點」，按字幕時間分段，保留具體事件、規則與例子。先選字幕依據再生成筆記，每項另做語意核對。沒有足夠依據的解讀改列「待核對原句」，不冒充結論；段落生成失敗會明示。時間連結由字幕引文定位，容許繁簡體與空白差異。長片採時間分散取樣並明確標示。新版共 33 項測試通過；AI 核對仍不能保證語意完全正確。

影片模式的逐項核對會增加處理時間與 API 呼叫次數；介面會顯示目前生成或核對到哪一段。僅略過短小、明確的結尾宣傳號召，原始字幕始終保留。

3.1.1 修正 HTTPS 憑證驗證與特殊文字造成的摘要卡住問題；本機 14 項測試通過。瀏覽器保留 Chromium sandbox。文字預處理最多使用前 500,000 字元，完整擷取原文仍保存。此程式不是網路防火牆，不提供內網隔離。

把來源變成重點。A local-first research assistant for webpages and YouTube.

貼上連結，取得可核對的閱讀報告：單篇摘要、影片時間點，或多篇文章的共通點與差異。繁體中文桌面介面，Crawl4AI 擷取網頁，Ollama 整理內容，Whisper 在本機辨識語音。

## 為什麼使用

- **影片不用手動找字幕**：優先讀取公開字幕；未提供字幕時，嘗試下載公開音訊並在本機轉錄，顯示進度。
- **跨來源比較**：共通點與差異必須引用至少兩份文件；引用不符合條件時顯示比較失敗。引用檢查不保證 AI 判讀正確。
- **保留證據**：原文、時間點、摘要與來源對照分開保存。報告內連結可回到來源。
- **選擇 AI 位置**：Ollama 使用本機模型；OpenAI API 或 Gemini API 使用自己的金鑰，開始前確認文字外傳與可能費用。基本摘錄不需要模型。
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

## 選擇 AI 與金鑰

在「設定與模型」選擇基本摘錄、Ollama、OpenAI API 或 Gemini API。

- 本機：啟動 Ollama，填已下載的模型 ID，或按「更新模型」選擇。
- 雲端：選供應商，按「API 金鑰」貼上自己的金鑰，再按「更新模型」或手動填入模型 ID。清單代表帳號可見模型，不保證每個模型都支援文字摘要與 JSON Schema；格式不支援時會顯示原因。
- 「僅本次」保留金鑰直到程式關閉；「安全儲存」寫入 Windows 認證管理員；「刪除已存金鑰」同時清除該供應商的程式內金鑰。切換供應商會保留各自模型設定。
- 每次開始雲端工作會確認外傳；傳送的是擷取文字、字幕及分段摘要，語音辨識仍在本機。金鑰不写入 settings.json、日誌或報告。
- API 可能依使用量計費，金鑰需由供應商開發者平台取得。此程式不讀取你的 ChatGPT 或 Gemini 網頁登入狀態。
- 連線或額度錯誤會停止本批後续 AI 請求，保留擷取原文和基本摘錄。修正設定後可用「貼上文字／字幕」重新摘要已保存原文。

此版固定連接官方 API 或本機 127.0.0.1，不接受自訂雲端端點。以帳號實際模型存取權限及供應商限制為準。

## 命令列

```powershell
.\.venv\Scripts\python cli.py https://example.com --basic
.\.venv\Scripts\python cli.py URL1 URL2 --model qwen2.5:7b
.\.venv\Scripts\python doctor.py
```

雲端 CLI：先透過桌面安全儲存金鑰，或在自己的執行環境設定 `OPENAI_API_KEY`／`GEMINI_API_KEY`（不要把金鑰放在命令列參數或分享的腳本）。

```powershell
.\.venv\Scripts\python cli.py URL --provider openai --model YOUR_MODEL_ID --allow-cloud
.\.venv\Scripts\python cli.py URL --provider gemini --model YOUR_MODEL_ID --allow-cloud
```

`--allow-cloud` 表示同意將內容傳至所選 API；未提供時不會開始雲端作業。API 金鑰沒有命令列輸入參數，避免出現在程序清單。

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
