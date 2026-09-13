# Product direction

The useful distinction is source-linked research, not the number of pages downloaded. A successful workflow ends with a report a reader can verify and use.

## Current architecture

`app.py` and `cli.py` → `engine.crawl_batch` → page or video extraction → selected AI summary → cross-source comparison → Markdown/JSON/CSV.

The extraction, model and UI modules are separate. `Page` is the shared result contract. `local_ai.py` routes both summary and comparison through `ai_providers.py`, retaining validation and bounded retries. `credentials.py` uses the Windows vault explicitly; the engine receives a transient provider object and never serializes credentials. Cloud adapters are in preview pending live-account acceptance.

## Next features, in priority order

1. **Research projects and changed-content reports**: save a source set and show what changed since the last run. Acceptance: new/deleted/modified evidence, previous report remains intact.
2. **Task templates**: product comparison, study notes, announcement tracking. Acceptance: task-specific fields and absent evidence shown explicitly.
3. **Local document import**: PDF, text and existing audio. Acceptance: consistent source/page/time citations and no cloud upload.
4. **Questions over a saved project**: answer only from selected saved sources, with supporting excerpts. Acceptance: unsupported questions return insufficient evidence.
5. **Signed installer and release builds**: reduce first-run friction after the quality and cancellation tests are stable.

Do not prioritize mass crawling, automatic posting, login-cookie collection or a large catalog of model providers before the existing report quality is dependable.

## What still needs evaluation

Citation semantic accuracy, multiple languages and accents, long videos, slow computers, false commonality between unrelated sources, installation on another physical Windows machine. Automated source-ID checks cannot replace these evaluations. Public interest requires feedback from real users; no usage or adoption is claimed.
