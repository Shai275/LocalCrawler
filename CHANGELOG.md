# Changelog

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
