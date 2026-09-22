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
# 3.2 preview validation — 2026-09-13

Video-summary update: 33 tests pass. Regression cases cover inherited timestamps, timeline sampling including the ending, generic statements and invented evidence, cross-block quote location, simplified/traditional equivalence, retaining valid items, and converting unsupported interpretations to explicitly labeled original text. Gemini generation and independent claim-check responses are simulated. Manual Ollama acceptance uses the public captions of `8NYdGenlji8`; cloud model quality still requires live-account testing. Model self-checks are fallible, not proof of factual correctness.

26 local tests passed, including all 3.1 regressions. New tests exercise Ollama/OpenAI/Gemini request and response contracts using simulated HTTP responses, citation rejection, bounded retries, auth/quota circuit breaking, cancellation propagation, raw export preservation, provider switching, decline-to-send, and non-persistence of secrets in preferences/reports.

Real integration checks: Windows Credential Manager store/read/delete used a unique disposable fake credential; installed Ollama qwen2.5:7b returned a source-linked summary through the new shared backend.

Not yet verified: live OpenAI/Gemini calls with a user's paid API credentials; arbitrary models listed by each account; complete cross-machine installation. Model listing does not establish JSON Schema compatibility. No cloud API key was used during automated tests. Current GitHub CI status is separate from local results.

## 3.3 frame validation — 2026-09-13

38 local tests pass. New cases cover bounded timeline sampling, timestamped Markdown galleries, OCR/caption overlap, Gemini multimodal request formatting, and existing worker cancellation cleanup. A real run against the user-supplied nine-minute video produced eight distinct JPEG key frames across the timeline. Offline RapidOCR read the on-screen phrase `阿伯我們拿了9分`; it matched the nearby caption and a local qwen2.5vl:3b request produced a report with separate visual, OCR, caption, timestamp and frame evidence. This acceptance did not call a paid cloud model; live cloud vision quality remains pending.


## 3.3 acceptance — 2026-09-21

The actual user-supplied video 8NYdGenlji8 produced 24,479 caption characters and eight OCR-processed frames. The initial stream fell back to software; selecting H.264 first activated verified D3D11 decoding for all eight frames on RTX 4060. Real local qwen2.5vl:3b output repeated captions; the new filter correctly omitted these as novel visual insights and exported source-only evidence with passing integrity checks. This is a fallback acceptance, not a claim of semantic chart understanding.

Regression coverage now includes temporal-only chart association, multiline transcript hashing on Windows, modified-HTML rejection through real Tk controls, and termination of descendant processes. Paid cloud model semantics, other operating systems, very long real videos, and global GPU/Ollama quotas remain outside this acceptance.

## 3.4 acceptance — 2026-09-21

Adaptive selection inspected a denser timeline of the public acceptance video and retained eight frames with full time coverage. Unlike uniform sampling, it selected a player-attribute radar chart and an interaction-control screen; all eight frames reported verified D3D11 decoding. Local qwen2.5vl:3b proposed attribute numbers absent from OCR/captions. The final validator rejected the entire note, retried once with the reason, then fell back to timestamped OCR text. This deliberately favors a reviewable omission over a fluent unsupported detail.

A controlled bar chart and workflow fixture verified OCR layout fallback. It recovered `Q1 ↔ 20`, `Q2 ↔ 35`, `Q3 ↔ 50`, `Q4 ↔ 45` and the order `CAPTURE → EXTRACT → VERIFY`. The small local vision model did not provide a reliable semantic trend, so the report retained these as position-derived hints requiring image review. Full regression: 52 tests passed. No macOS/Linux or paid-cloud semantic acceptance is claimed.
