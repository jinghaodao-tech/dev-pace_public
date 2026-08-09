# dev-pace PCS adapter

External client for submitting the privacy-reduced daily JSONL produced by
dev-pace to PCS `POST /v1/integration-imports`.

The adapter sends only:

- daily activity minutes
- AI conversation minutes
- deep thinking minutes
- window switch count
- idle and away minutes
- date, a 24-hour `hourly_active_minutes` vector, and measurement provenance

It never sends application names, window titles, source filenames, or raw
record counts. A dry run is the default; network submission requires explicit
`--url`, `--client-id`, and `--token`.

```powershell
python adapter.py --input C:\Users\jingh\TLA\dev-pace\outputs\activity_daily.jsonl --output outputs\pcs_imports.jsonl
```

## Daily submission

Set `PCS_API_URL`, `PCS_CLIENT_ID`, and `PCS_CLIENT_TOKEN` as persistent
environment variables for the Windows user that owns the scheduled task. The
token is read at runtime and is never stored in this repository.

Run the complete pipeline once:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_daily_pipeline.ps1
```

Register the daily task (default 00:05 local time):

```powershell
powershell -ExecutionPolicy Bypass -File .\register-daily-task.ps1
```

The task aggregates local logs, rewrites the privacy-reduced daily JSONL, and
submits it through the external `submit_import` client.
