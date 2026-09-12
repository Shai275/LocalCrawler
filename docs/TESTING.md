# Testing

## 3.1.1 security regression

All 14 tests passed locally on Windows/Python 3.12. The added tests verify a 500,000-character malformed bracket input finishes in a bounded subprocess and that real Chromium crawling rejects a self-signed HTTPS server. The first certificate test exposed Chromium launch flags that bypassed the context setting; `secure_browser.py` removes those flags, enables Chromium sandbox, and requires a fresh dedicated browser. This adapter is tied to pinned Crawl4AI 0.9.3; re-run the HTTPS test before dependency upgrades. No claim of private-network isolation or full dependency security review is made.

Run `python -m unittest discover -s tests -v` after installing requirements and Playwright Chromium.

Tests cover real local HTTP/Chromium rendering, robots rules, transient retries, error export, saved history validation, real Tk widgets, AI schema validation, comparison requiring distinct documents, and cancellation of an actual subprocess with a partially written audio file. Mock model responses keep CI independent of GPU availability and public video access.

Manual acceptance includes an actual public YouTube link without subtitles, real Ollama inference, two public Python documentation pages, and a controlled pair of synthetic sources whose differences are known. Report a fallback as a fallback, not AI success. Check the report itself for incorrect names, unsupported facts and source coverage.

The Windows workflow is configured in `.github/workflows/test.yml`. It has not been run on GitHub until the repository is uploaded and Actions executes there. No credentials, private browsing data or downloaded content should enter the repository.

## Local acceptance — 2026-09-12

- Windows, Python 3.12.10, fresh project virtual environment: all 12 tests passed.
- Crawl4AI 0.9.3 with installed Playwright Chromium rendered the local JavaScript fixture.
- Public YouTube video `mZUewl7DbUE`: public subtitles were unavailable; audio transcription with faster-whisper small (CPU int8), followed by real Ollama qwen2.5:7b inference, produced saved transcript, summary and timestamp sources successfully.
- Python tutorial on virtual environments and PyPA's pip/virtual-environments guide: both fetched and summarized; the cross-document comparison produced references to distinct documents.
- A controlled pair with known prices, dates and conditions produced the expected common point and differences.
- Real desktop interaction: advanced controls collapsed by default, model selection and example.com summary worked; saved history and report preview were checked.

These results establish working flows, not factual accuracy certification. The video report still contained incorrectly recognized product names and an incorrect derived weight difference. Always check names and numerical conclusions against original timestamps. Automated tests use controlled model replies and cannot measure general model quality. External site restrictions, model availability and hardware affect results.
