from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

FIELDS = ("active_minutes", "ai_conversation_minutes", "deep_thinking_minutes", "window_switch_count", "idle_minutes", "away_minutes")


def build_import(record: dict, tool_version: str) -> dict:
    date = record.get("date")
    if not isinstance(date, str) or not date:
        raise ValueError("daily_record_date_required")
    measured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {key: record.get(key, 0) for key in FIELDS}
    payload["hourly_active_minutes"] = json.dumps(record.get("hourly_active_minutes", [0.0] * 24), separators=(",", ":"))
    payload.update({"date": date, "measurement": {"definitionVersion": "dev-pace-daily-v1", "sourceTool": "dev-pace", "sourceToolVersion": tool_version, "measuredAt": measured_at}})
    return {"id": f"dev-pace-day-{date}", "sourceSystem": "dev_pace", "sourceReferenceId": date, "payload": payload, "createdAt": measured_at}


def submit(base_url: str, client_id: str, token: str, value: dict) -> dict:
    request = Request(base_url.rstrip("/") + "/v1/integration-imports", data=json.dumps(value).encode("utf-8"), headers={"content-type": "application/json", "x-pcs-client-id": client_id, "authorization": f"Bearer {token}"}, method="POST")
    try:
        with urlopen(request, timeout=15) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError) as error:
        raise RuntimeError(f"pcs_import_failed: {error}") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit privacy-reduced dev-pace daily summaries to PCS.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--url")
    parser.add_argument("--client-id")
    parser.add_argument("--token")
    parser.add_argument("--tool-version", default="0.1.0")
    args = parser.parse_args()
    with args.input.open("r", encoding="utf-8") as handle:
        values = [build_import(json.loads(line), args.tool_version) for line in handle if line.strip()]
    url = args.url or os.environ.get("PCS_API_URL")
    client_id = args.client_id or os.environ.get("PCS_CLIENT_ID")
    token = args.token or os.environ.get("PCS_CLIENT_TOKEN")
    if url:
        if not client_id or not token:
            parser.error("--client-id and --token are required with --url")
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("w", encoding="utf-8", newline="\n") as handle:
                for value in values:
                    handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
        print(json.dumps({"submitted": len(values), "results": [submit(url, client_id, token, value) for value in values]}))
        return
    if not args.output:
        parser.error("--output is required for a dry run")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for value in values:
            handle.write(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"prepared": len(values), "output": str(args.output)}))


if __name__ == "__main__":
    main()
