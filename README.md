# LocalCrawler 3.4 — 智慧影格與圖表線索預覽版

貼上網頁或 YouTube 連結，整理大綱、重點，或比較多個來源的共通點與差異。可選本機 Ollama、OpenAI 或 Gemini；基本摘錄不需要 AI。

## 3.4 新功能

- 可選「影片畫面理解」：下載最高 720p、90 分鐘／300 MB 以內的公開影片。程式先檢查最多 48 個候選時間點，依畫面變化、清晰度及時間覆蓋智慧挑選最多 12 張，不增加 AI 圖片上限。
- 優先相容的 H.264 串流。PyAV 確認硬體解碼已啟用才標示成功；Windows 嘗試 D3D11，失敗自動軟體回退。其他作業系統尚未實測。
- 影格實際播放時間與字幕小數秒、持續時間分開保存。共同文字與「僅時間相鄰」分別標示，兩者都不代表 AI 結論已核實。
- OCR 會保存文字座標與可信度。AI 無法讀懂圖表時，仍可列出 `Q1 ↔ 20` 或 `CAPTURE → EXTRACT → VERIFY` 等位置線索，並清楚標示需要人工核對。
- 相似度檢查會排除原句及換句話說的字幕；AI 描述中的數字若未出現在 OCR 或字幕也會被拒絕。無可靠補充時改列有時間連結的 OCR 可見文字，仍保留影格與來源核對頁。
- 新的來源頁提供時間軸、交叉文字／僅時間相鄰統計與解碼狀態。開啟前會檢查字幕、影格、擷取資料與 HTML 的 SHA-256。

Windows 本機可使用已安裝的圖片模型，例如 `qwen2.5vl:3b`；在「設定與模型」勾選「影片畫面理解」並填入視覺模型名稱。功能預設關閉。雲端模式開始前會提示文字與最多 12 張圖片傳送及可能費用。

## 資源保護與驗證範圍

影片工作程序及子程序以 250 ms 間隔監測：CPU 約全機 40% 軟性限流，RSS 合計超過實體 RAM 25% 或 2 GiB（取較小者）即停止。計算庫最多兩條執行緒，支援平台會限制核心並降低優先序。取消時終止工作程序樹並清理暫存下載。

這不是 Chromium、外部 Ollama 或 GPU 的全域配額，也不保證所有機器不當機。雜湊能核對保存後的檔案變化，不提供來源真實性、可信時間戳或司法認證。

2026-09-21：Windows／RTX 4060 上，使用者指定的實際影片成功取得字幕及 8 張硬體解碼影格，智慧挑選捕捉到雷達圖與遊戲操作畫面。本機 qwen2.5vl:3b 對雷達圖提出了無 OCR／字幕支持的數字，因此被完整拒絕並回退到可點擊 OCR 來源。受控長條圖由 OCR 版面正確列出 `Q1 ↔ 20、Q2 ↔ 35、Q3 ↔ 50、Q4 ↔ 45`；小型視覺模型沒有可靠產生趨勢結論，因此本版不宣稱已通過圖表語義品質驗收。雲端視覺使用模擬 API 測試，尚未做付費帳號品質驗收。

## 為什麼使用

- **影片不用手動找字幕**：優先讀取公開字幕；未提供字幕時，嘗試下載公開音訊並在本機轉錄，顯示進度。
- **跨來源比較**：共通點與差異必須引用至少兩份文件；引用不符合條件時顯示比較失敗。引用檢查不保證 AI 判讀正確。
- **保留證據**：原文、時間點、摘要與來源對照分開保存。報告內連結可回到來源。
- **選擇 AI 位置**：Ollama 使用本機模型；OpenAI API 或 Gemini API 使用自己的金鑰，開始前確認文字外傳與可能費用。基本摘錄不需要模型。
- **桌面與 CLI 共用流程**：方便日常操作，也能接入自己的研究腳本。
- **一鍵變成交付成果**：在任何摘要、來源對照或整批比較旁按「一鍵匯出成果」，同時建立排版 PDF、含圖片的 Markdown、可直接匯入 Notion 的 ZIP，以及可在 Obsidian 開啟的 Canvas 知識圖。每份成果附來源雜湊清單。

## 開始使用（Windows / Python 3.12）

若使用 Windows EXE 資料夾版，解壓縮後直接執行 `LocalCrawler.exe`。請保留 `_internal` 與 `LocalCrawlerWorker.exe`；設定、日誌與研究成果保存在 `%LOCALAPPDATA%\LocalCrawler`，更換新版程式資料夾不會覆蓋它們。

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

選好要交付的報告後按「一鍵匯出成果」。輸出位於該次研究資料夾的 `deliverables/`：PDF 可直接傳閱；`notion-import.zip` 可由 Notion 的 Markdown 匯入功能解壓或匯入；`markdown/` 保留可攜圖片；`obsidian/` 整個複製進 Vault 後開啟 `.canvas`。

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

這是研究輔助工具，AI 來源編號通過格式檢查不代表語意一定正確。語音辨識可能聽錯人名、產品名或數字；重要結論請點擊時間點核對。畫面理解採最多 12 張抽樣，不代表看過每一秒；視覺模型仍可能誤判。

音訊限可公開取得、非直播、90 分鐘內且下載小於 120 MB 的影片。遇到登入、私密影片、平台封鎖、驗證碼或 robots.txt 禁止時會停止該來源，不使用 Cookie 或代理繞過限制。

單篇 AI 最多分析前約 36,000 字元；分段摘要保留在報告後方。比較會為各來源分配等額文字預算，並標示只比較選取內容。原文不會因此截短。每批最多 100 個網址；只擷取輸入頁面，不自動遍歷整站。Windows 已測試；其他系統的桌面啟動尚未驗證。

## 開發與授權

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
```

參考 [貢獻指南](CONTRIBUTING.md)、[架構與路線圖](docs/ROADMAP.md)、[測試說明](docs/TESTING.md)。GitHub Actions 設定會在 Windows 執行測試；本機準備發布包不代表已執行雲端 CI。

本專案程式碼採 MIT 授權。依賴套件、語音／語言模型與擷取內容仍遵循各自授權，不隨本專案重新授權。

使用的開源工具：[Crawl4AI](https://github.com/unclecode/crawl4ai)、[YouTube Transcript API](https://github.com/jdepoix/youtube-transcript-api)、[yt-dlp](https://github.com/yt-dlp/yt-dlp)、[faster-whisper](https://github.com/SYSTRAN/faster-whisper)、[Ollama](https://github.com/ollama/ollama)。
