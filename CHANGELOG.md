# Changelog

## 3.1.1 — 2026-09-12

- Enforce HTTPS certificate verification, remove Chromium certificate bypass flags, and retain Chromium sandbox.
- Prevent repeated unmatched brackets from causing quadratic Markdown parsing; cap analysis preprocessing at 500,000 characters and disclose truncation.
- Add real self-signed HTTPS rejection and malformed-text regression tests. All 14 tests pass locally.
- Include Windows setup, desktop/CLI workflows, source-linked video notes, multi-source comparison, contribution documentation and CI.

Known limitations: speech recognition and AI summaries can misstate names or numbers; verify original evidence. This is a local desktop tool, not a network-isolation firewall. Cloud CI and release publication status are shown by GitHub.
