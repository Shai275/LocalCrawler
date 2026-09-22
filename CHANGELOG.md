# Changelog

## 3.4 preview — 2026-09-21

- Redesign the desktop interface as a dark three-pane research workspace: source controls on the left, a document-width synthesis reader in the center, and searchable evidence/results on the right. Provider badges distinguish local processing from opt-in cloud APIs, and the compact settings view remains usable at the 1120×720 minimum window size.
- Reduce the self-contained Windows bundle from 1,091.1 MB to 806.6 MB and its ZIP from 480.3 MB to 368.7 MB. The build omits unused Patchright, SciPy and NLTK payloads, duplicate OpenCV FFmpeg DLLs, and Chromium locale packs outside English and Chinese while retaining bundled Chromium, Playwright, PyAV, Whisper and OCR.
- Add a reproducible Windows x64 PyInstaller onedir build with bundled headless Chromium and a separate resource-limited video worker. User settings, logs and research results live under `%LOCALAPPDATA%\LocalCrawler` so replacing the program folder preserves them.
- Add one-click delivery export for styled PDF, portable Markdown, a Notion import ZIP, and an Obsidian Canvas with section cards and local assets.
- Inspect up to 48 bounded candidates, reject blank and near-duplicate frames, and retain the highest-information frame per time segment. The AI upload cap remains 12.
- Store OCR text coordinates and confidence. Produce conservative label/value pairs and horizontal sequences when a small vision model cannot explain a chart or workflow.
- Reject close paraphrases of captions and numbers absent from OCR/captions; fall back to timestamped visible OCR text rather than unsupported visual claims.
- Add an evidence timeline, source-association counts and verified decoder status to the local HTML report.
- Real Windows acceptance selected a radar chart from the user-supplied video with eight D3D11-decoded frames. A controlled chart recovered four intended label/value pairs; its semantic trend remained unverified.

## 3.3 preview — 2026-09-21 validation update

- Verify actual PyAV hardware decoding before reporting acceleration; prefer H.264 streams and retain software fallback. The user-supplied YouTube acceptance video produced eight hardware-decoded frames on Windows / RTX 4060.
- Preserve frame PTS and fractional caption intervals; distinguish text overlap from temporal-only associations. Charts no longer require identical OCR and spoken text.
- Reject verbatim caption repetition as new visual insight. Preserve a navigable source-only report when visual interpretation adds nothing or fails.
- Verify transcript, images, capture metadata and HTML before opening the evidence viewer. Fix Windows newline hashing and cover modified-report rejection in the real Tk UI.
- Test cancellation of descendant processes, bounded CPU/RSS behavior and decoding. Platform coverage remains Windows; cloud semantic quality is not live-account validated.

## 3.3 preview — 2026-09-13

- Add opt-in key-frame extraction for public YouTube videos: 720p maximum, 90-minute/300-MB limits, duplicate and blank-frame filtering, and at most 12 retained JPEGs.
- Add multimodal Ollama, OpenAI and Gemini requests for visible slide text, chart trends, numbers and interface actions. Reports retain frame images and timestamp links when visual AI is unavailable.
- Add offline RapidOCR and pair each frame with nearby captions. Later updates distinguish shared text from time-only associations; neither certifies AI conclusions.
- Keep frame analysis disabled by default and disclose cloud image transmission before each cloud run.

## 3.2 preview — 2026-09-13

- Add chronological video outlines and concrete notes with caption evidence. Locate evidence across adjacent caption blocks, normalize Chinese script variants, retain timestamps, and avoid lossy final merging.
- Add independent claim checks. Unsupported interpretations are shown as explicitly labeled raw excerpts; valid items survive adjacent malformed items. Generation and checking remain cancellable and use the selected provider.
- 33 local tests pass including Gemini video request/response contracts; real Ollama acceptance uses the user-supplied video 8NYdGenlji8. Cloud semantic quality still requires live-account acceptance.

- Unify source-linked summary and comparison generation across Ollama, OpenAI Chat Completions and Gemini Generate Content.
- Add provider/model selection, model listing, explicit cloud-send confirmation and per-provider model preferences.
- Add session-only keys or explicit Windows Credential Manager storage/deletion; no plaintext settings fallback.
- Add CLI provider/model selection and required cloud consent flag; credentials supplied through environment or vault.
- Sanitize service errors, stop further API requests after connection/auth/quota failure, and preserve raw research results.
- 26 local tests passed; local Ollama generation and real Windows vault roundtrip verified. Cloud behavior is verified with simulated responses, not paid live API calls. Preview until live account acceptance is complete.

## 3.1.1 — 2026-09-12

- Enforce HTTPS certificate verification, remove Chromium certificate bypass flags, and retain Chromium sandbox.
- Prevent repeated unmatched brackets from causing quadratic Markdown parsing; cap analysis preprocessing at 500,000 characters and disclose truncation.
- Add real self-signed HTTPS rejection and malformed-text regression tests. All 14 tests pass locally.
- Include Windows setup, desktop/CLI workflows, source-linked video notes, multi-source comparison, contribution documentation and CI.

Known limitations: speech recognition and AI summaries can misstate names or numbers; verify original evidence. This is a local desktop tool, not a network-isolation firewall. Cloud CI and release publication status are shown by GitHub.
