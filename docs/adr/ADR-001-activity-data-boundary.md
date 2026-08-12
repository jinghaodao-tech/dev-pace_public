# ADR-001: Activity aggregation and privacy boundary

## Decision

Raw JSONL activity logs remain local and are not sent to PCS. The PCS
intermediate format is one record per day and contains only application names,
durations, state durations, switch counts, and first/last
activity timestamps.

Window titles are treated as sensitive local telemetry. The aggregation step
removes page titles, file names, URLs, and document names by mapping each title
to an application name. The raw logs are retained only for local diagnostics.

The aggregator accepts both legacy records with `window` and current records
with `main_window` / `distribution`. New recorder output is marked `v: 2`.

`DeepThinking` is assigned only after 60 seconds without input when the active
window is a work or reading application. Games, video, lock screens, system
surfaces, and notifications become `Idle` instead. After 20 minutes the state
is `Away`. Recent input in an AI window is recorded as `AIConversation`, not
`DeepThinking`. This prevents merely opening an AI window, or typing rapidly,
from inflating the thinking-time metric. The same rule is applied when
aggregating historical records.

## Rationale

Application-level time and switching behavior are sufficient for testing
activity hypotheses while page and file titles are unnecessary disclosure.
Daily aggregation also keeps the PCS contract stable as the recorder changes.
