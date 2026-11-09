# SuishouReply v1.1.0 Implementation Plan

> **For agentic workers:** Use test-driven implementation and independent review of the integrated result.

**Goal:** Add a one-click original Chinese X post workflow for AI信号局 while retaining the reply assistant.

**Architecture:** Keep the native Qt window and existing reply controller. Add a separate original-post controller, local inspiration/history domain and bounded asynchronous official-news client. Both writing workflows reuse DeepSeekClient and CredentialStore; mode switches cancel pending generation so only one writing workflow runs at a time.

**Tech Stack:** Python 3.14, PySide6 Essentials / QtNetwork, standard-library JSON/XML, PyInstaller.

**Spec:** User request in this chat dated 2026-11-09; detailed implementation decisions below. User explicitly requested direct implementation without a design approval stop.

## Global constraints

- Keep clipboard listening off at startup; no copied-tweet persistence or automatic X actions.
- Original posts: one result, Chinese 50–110 characters preferred, 1–3 sentences, conservative X weighted length at most 280 including optional source URL.
- Random styles select 犀利 / 幽默 / 反常识; only explicit 热点 performs public-news requests.
- Store at least 50 recent original results separately from settings; favorites and published flags are local only. Clear history available.
- Official news needs title, original URL, verifiable timestamp and source description/release body; maximum age 14 days, no future/stale fallback.
- Keep API key only in existing Windows Credential Manager; no automatic model retry, cancel and discard stale responses.

## Review focus

- Copying an original result must not trigger paid reply generation, including clipboard-history restoration.
- Changing page, settings or selections during a request must not allow late responses to overwrite current content.
- Malformed structured output, oversized content and fabricated source URLs must be rejected.
- Unwritable/corrupt history must be visible and must not silently erase existing data.
- Small screens, long source titles and source failure must leave actions accessible.

## Tasks

- [x] Domain: inspiration pool, structured prompts, output/length validation and bounded duplicate detection; tests for all style/topic combinations, copied source length, invalid output and history persistence.
- [x] Official sources: verify endpoints live, parse dated trustworthy summaries, asynchronous timeout/cancellation/fallback; tests with local responses for stale, future, malformed and unreachable sources.
- [x] UI: add two modes, original result/source cards, copy/favorite/published/history actions while preserving non-activating popup; tests for loading, errors, selection and layout.
- [x] Integration: extend DeepSeekClient with JSON original generation, add OriginalController, coordinate modes/clipboard/settings/cancellation; regression tests plus simulated complete flow.
- [x] Delivery: v1.1.0 resources, README/changelog/privacy/source documentation; native source and EXE self-tests, actual Windows screenshots, clean release archive/checksum and local Git commit preserving history.

## Interfaces

`original.py`: choose_seed(style, topic, history, rng=None), build_original_messages(seed, recent, source=None), parse_post(raw, seed, source=None), weighted_length(text).

`history.py`: HistoryStore(path=None), records, recent(limit=50), is_duplicate(body), add(post, seed), update(record_id, **flags), clear().

`news.py`: NewsClient.fetch(request_id, topic='随机'), cancel(); succeeded(int,list), failed(int,str). Source dictionaries contain title, published_at, url, summary, provider.

`original_ui.py`: OriginalPage signals for generate/cancel/copy/favorite/published/history/clear/record selection; show_loading/show_post/show_error/show_idle/show_copied/set_busy/show_history.

`ui.py`: ReplyWindow.original_page, set_mode('reply'|'original'), mode_changed(str); existing reply methods remain compatible.
