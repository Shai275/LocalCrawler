# Contributing

Use Python 3.12 on Windows. Run `setup.ps1`, then `.venv\Scripts\python -m unittest discover -s tests -v`.
Tests use a local HTTP fixture and mocked model responses; they require Chromium and a desktop-capable Windows session but no Ollama model or YouTube login.

Keep network extraction in `engine.py` / `video.py`, inference in `insights.py` / `comparison.py` / `local_ai.py`, and UI state in `app.py`. Both desktop and CLI call `crawl_batch`.

New extractors should return a `Page`, preserve original content before inference, report progress, and respect cancellation. Test blocked sources, missing content and partial failure as well as success. Never commit downloads, settings, cookies, credentials or audio files.

For a bug report include OS, Python version, `doctor.py` output, reproduction steps and expected/actual behavior. Remove private URLs before sharing logs. For AI quality reports include a small public or synthetic example and the cited source excerpts. Do not treat matching citation IDs as proof that a claim is true.
