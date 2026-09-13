# LocalCrawler 3.2 AI providers — checkpoint

2026-09-13：已完成可執行的 3.2 預覽版，主程式已接入統一後端。

已接入基本摘錄、Ollama、OpenAI 與 Gemini 的單篇摘要與多來源比較。桌面可切換供應商與模型、更新模型清單、管理金鑰；CLI 支援 --provider、--model、--allow-cloud。

26 項測試已通過；包含模擬雲端回覆、錯誤與額度停止、來源驗證、取消、原文保存、介面切換和拒絕外傳。另已實測真實 Ollama qwen2.5:7b 摘要及 Windows 金鑰寫入／讀取／刪除（使用獨立測試項目，不讀取個人金鑰）。

金鑰已使用 Windows Credential Manager，亦可選擇只存本次記憶體。不寫入 settings.json、日誌、報告或版本庫。

待驗證：使用者在程式中填入自己的 OpenAI／Gemini API 金鑰後，各跑一次真實摘要與雙來源比較。尚未有真實雲端 API 呼叫證據，預覽版不得宣稱已完成雲端帳號驗收。此版不支援自訂端點、精確費用預估或完整模型相容性自動辨識。

文件依據：
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- https://keyring.readthedocs.io/en/latest/
