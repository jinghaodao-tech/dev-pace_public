# Idle State Redefinition: Separating Rest from Thinking

## Problem

The recorder's first priority was simple: treat any period with no keyboard or
mouse input as "idle," because raw active/inactive time alone is not useful
for testing activity hypotheses. But a period with no input events is not one
thing. Stepping away from the desk (a break) and staring at a document while
composing a thought (still working, just not producing input) both look
identical to an input-only detector. Collapsing both into one `Idle` bucket
would distort any downstream analysis that treats idle time as "not working."

## Current implementation

State is a plain `String` field on `ActivityLog` (`src/main.rs:36`), not a
Rust enum, with five values in practice: `Active`, `AIConversation`,
`DeepThinking`, `Idle`, `Away`. The state for a given sampling window is
decided from a single input: `elapsed`, the number of seconds since the last
keyboard/mouse event, captured once per 60-second batch (`src/main.rs:283`).

```
elapsed >= 1200                                  -> Away
elapsed <  60 && foreground window is an AI site  -> AIConversation
elapsed <  60                                     -> Active
elapsed >= 60 && foreground window is work/reading -> DeepThinking
otherwise                                          -> Idle
```

(`src/main.rs:284-294`; thresholds `60` and `1200` are inline literals, not
named constants, and are not configurable.)

The `DeepThinking` classification is what actually separates "resting" from
"thinking": after 60 seconds without input, the foreground window's title is
checked against an allowlist (`is_thinking_window`, `src/main.rs:134-165`) of
work/reading applications (browsers, editors, terminal, Obsidian, office
apps, AI sites). If the foreground app is on that list, the no-input period
is recorded as `DeepThinking` instead of `Idle`. After 20 minutes with no
input, the state becomes `Away` regardless of foreground window, on the
assumption that a pause that long is a real break even if the screen shows a
work app left open.

`AIConversation` is a separate carve-out for input seen inside an AI window
within the last 60 seconds, so that opening a chat tool or typing into it
does not get folded into either `Active` or `DeepThinking` (see
`docs/adr/ADR-001-activity-data-boundary.md`, which documents this same
threshold set from the privacy/aggregation-boundary angle).

## What this design decision actually is

The distinction between "break" and "thinking" is made **by content
(which application is in the foreground), not by duration**. There is no
presence sensor, camera, or additional input source — only the window
title, matched against a fixed allowlist, the same mechanism `dev-pace`
already uses elsewhere to avoid storing raw titles. This keeps the idle
classification consistent with the project's existing privacy stance: no
new signal is introduced, an existing one (foreground app identity) is
reused for a second purpose.

Two duration thresholds bound the classification: below 60 seconds, no
input is not yet treated as unusual at all (`Active`); above 20 minutes, no
input is treated as a real break regardless of context (`Away`). Between
those two bounds, the foreground application decides.

## Known gap (not fixed by this document)

Within the 60-second to 20-minute band, there is no further split by
duration. A 90-second pause and an 18-minute pause in an allowlisted
application both record as `DeepThinking` with no distinction between them,
and the same is true for two very different pause lengths that land in
`Idle`. The current design answers "was this plausibly still work?" but not
"how long was the pause?" within that band.

Downstream, `tools/aggregate_activity.py` collapses the five states into
daily minute totals (`active_minutes`, `ai_conversation_minutes`,
`deep_thinking_minutes`, `idle_minutes`, `away_minutes`), and the
app-title-derived detail (which specific application was in the
foreground) is dropped before the data reaches PCS — that per-app detail is
genuinely not observable downstream.

**Update (2026-08-15):** the five-state split itself, including the
thinking/break distinction, *does* reach MeTheory — `deep_thinking_minutes`
is a required field in the `dev-pace-daily-v1` PCS template
(`apps/api/src/routes/content.ts` in Personal-Context-Studio) and MeTheory's
`pcsSnapshotAnalysis.ts` derives a `deep_thinking_ratio` from it, used as
the outcome of a real correlation analysis. This section previously said
otherwise; that was stale. Reading MeTheory's actual code (rather than
trusting this doc) surfaced a different, real bug in how that ratio's
denominator was computed — see
`MeTheory-main-merge/docs/adr/ADR-016-total-observed-definition.md`.

## Rejected alternatives

- **Presence detection (camera, proximity sensor).** Adds a new sensor and
  a materially different privacy posture for a marginal gain; rejected as
  out of proportion to the problem.
- **OS-level idle API only (no foreground-window check).** This is exactly
  the original problem being fixed — it cannot distinguish a break from
  reading/thinking, since both produce zero input events.
- **Full window-title logging for later reclassification.** Would let a
  future change re-derive better states from history, but violates the
  existing "titles are sensitive, map to app name only" boundary
  (ADR-001) for a feature that is not committed to being built.

## Status

Implemented at the recorder level (three-band classification with an
application allowlist), and the thinking/break distinction does propagate
to PCS and MeTheory (see the 2026-08-15 update above). Not implemented: any
further duration-based split within the `DeepThinking`/`Idle` band. That
remains open, not silently dropped.
