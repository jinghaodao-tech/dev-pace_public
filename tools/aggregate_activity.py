from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Iterable
from zoneinfo import ZoneInfo


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def load_records(paths: Iterable[Path]) -> list[tuple[Path, dict]]:
    records: list[tuple[Path, dict]] = []
    for path in paths:
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(value, dict) and parse_timestamp(value.get("timestamp")):
                        records.append((path, value))
        except OSError:
            continue
    records.sort(key=lambda item: parse_timestamp(item[1]["timestamp"]) or datetime.min)
    return records


def discover_logs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if not input_path.exists():
        return []
    return sorted(input_path.glob("activity_*.jsonl"))


def application_name(title: object) -> str:
    text = str(title or "").strip()
    lower = text.lower()
    if not text:
        return "Unknown"
    if "google chrome" in lower:
        return "Google Chrome"
    if "microsoft edge" in lower:
        return "Microsoft Edge"
    if "mozilla firefox" in lower:
        return "Mozilla Firefox"
    if "brave" in lower:
        return "Brave"
    if "visual studio code" in lower or "vs code" in lower:
        return "Visual Studio Code"
    if "windows powershell" in lower or "powershell" in lower:
        return "Windows PowerShell"
    if "windows terminal" in lower:
        return "Windows Terminal"
    if "github desktop" in lower:
        return "GitHub Desktop"
    if "obsidian" in lower:
        return "Obsidian"
    if "codex" in lower:
        return "Codex"
    if "the sims" in lower:
        return "The Sims 4"
    if "chatgpt" in lower:
        return "ChatGPT"
    if "claude" in lower:
        return "Claude"
    if "gemini" in lower:
        return "Gemini"
    if "perplexity" in lower:
        return "Perplexity"
    if "copilot" in lower:
        return "Copilot"
    if "powerpoint" in lower:
        return "PowerPoint"
    if "word" in lower:
        return "Microsoft Word"
    if "excel" in lower:
        return "Microsoft Excel"
    if "discord" in lower:
        return "Discord"
    if "ubuntu" in lower:
        return "Ubuntu"
    if "task manager" in lower or "タスク マネージャー" in text or "タスク 繝槭ロ繝ｼ繧ｸ繝｣繝ｼ" in text:
        return "Task Manager"
    if "clipchamp" in lower:
        return "Microsoft Clipchamp"
    if "cmd.exe" in lower or lower == "cmd":
        return "Command Prompt"
    if "settings" in lower or "設定" in text:
        return "Windows Settings"
    if "task view" in lower or "タスク ビュー" in text:
        return "Task View"
    if "lock screen" in lower or "ロック画面" in text:
        return "Windows Lock Screen"
    if "steam" in lower:
        return "Steam"
    if "notification" in lower or "通知" in text:
        return "Windows Notifications"
    if "shell experience host" in lower or "シェル エクスペリエンス" in text:
        return "Windows Shell"
    if "onedrive" in lower:
        return "OneDrive"
    if "file picker" in lower or "ファイルを選択" in text or "開く" == text:
        return "File Picker"
    if "snipping tool" in lower or "snipping" in lower:
        return "Snipping Tool"
    if "windows security" in lower or "windows セキュリティ" in lower:
        return "Windows Security"
    if "ollama" in lower:
        return "Ollama"
    if "youtube" in lower:
        return "YouTube"
    if "explorer" in lower or "エクスプローラー" in text:
        return "File Explorer"
    if "notepad" in lower:
        return "Notepad"
    return "Other"


def is_thinking_window(title: object) -> bool:
    lower = str(title or "").lower()
    excluded = ("youtube", "steam", "the sims", "lock screen", "task view", "clipchamp", "notification")
    if any(value in lower for value in excluded):
        return False
    allowed = (
        "google chrome", "microsoft edge", "mozilla firefox", "visual studio code",
        "vs code", "codex", "chatgpt", "claude", "gemini", "perplexity", "copilot",
        "powershell", "windows terminal", "obsidian", "word", "powerpoint", "excel", "ubuntu",
    )
    return any(value in lower for value in allowed)


def is_ai_window(title: object) -> bool:
    lower = str(title or "").lower()
    return any(value in lower for value in ("chatgpt", "claude", "codex", "gemini", "perplexity", "copilot", "[web-ai:"))


def normalized_state(record: dict) -> str:
    state = str(record.get("state", "Unknown"))
    title = record.get("main_window") or record.get("window") or "Unknown"
    if state == "Active" and is_ai_window(title):
        return "AIConversation"
    if state == "DeepThinking" and not is_thinking_window(title):
        return "Idle"
    return state


def record_distribution(record: dict) -> dict[str, float]:
    distribution = record.get("distribution")
    if isinstance(distribution, dict) and distribution:
        return {application_name(title): float(value or 0) / 60.0 for title, value in distribution.items()}
    title = record.get("main_window") or record.get("window") or "Unknown"
    return {application_name(title): 1.0}


def aggregate(records: list[tuple[Path, dict]], timezone_name: str = "Asia/Tokyo") -> list[dict]:
    timezone = ZoneInfo(timezone_name)
    days: dict[str, dict] = {}
    previous_app: str | None = None
    for source_path, record in records:
        timestamp = parse_timestamp(record.get("timestamp"))
        if timestamp is None:
            continue
        local_timestamp = timestamp.replace(tzinfo=timezone)
        day = local_timestamp.date().isoformat()
        result = days.setdefault(day, {
            "v": 1,
            "date": day,
            "total_observed_minutes": 0.0,
            "active_minutes": 0.0,
            "ai_conversation_minutes": 0.0,
            "deep_thinking_minutes": 0.0,
            "idle_minutes": 0.0,
            "away_minutes": 0.0,
            "hourly_active_minutes": [0.0] * 24,
            "app_breakdown": defaultdict(float),
            "window_switch_count": 0,
            "first_activity_at": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "last_activity_at": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "record_count": 0,
            "source_files": set(),
        })
        result["last_activity_at"] = local_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        result["record_count"] += 1
        result["source_files"].add(source_path.name)

        distribution = record_distribution(record)
        observed = sum(distribution.values()) or 1.0
        state = normalized_state(record)
        result["total_observed_minutes"] += observed
        if state == "Active":
            result["active_minutes"] += observed
        elif state == "AIConversation":
            result["ai_conversation_minutes"] += observed
        elif state == "DeepThinking":
            result["deep_thinking_minutes"] += observed
        elif state == "Idle":
            result["idle_minutes"] += observed
        elif state == "Away":
            result["away_minutes"] += observed
        if state in {"Active", "AIConversation", "DeepThinking"}:
            result["hourly_active_minutes"][local_timestamp.hour] += observed
        for app, minutes in distribution.items():
            result["app_breakdown"][app] += minutes

        main_title = record.get("main_window") or record.get("window") or "Unknown"
        main_app = application_name(main_title)
        if previous_app is not None and main_app != previous_app:
            result["window_switch_count"] += 1
        previous_app = main_app

    output = []
    for day in sorted(days):
        result = days[day]
        result["app_breakdown"] = {
            key: round(value, 2)
            for key, value in sorted(result["app_breakdown"].items(), key=lambda item: (-item[1], item[0]))
        }
        result["source_files"] = sorted(result["source_files"])
        for key in ("total_observed_minutes", "active_minutes", "ai_conversation_minutes", "deep_thinking_minutes", "idle_minutes", "away_minutes"):
            result[key] = round(result[key], 2)
        result["hourly_active_minutes"] = [round(value, 2) for value in result["hourly_active_minutes"]]
        output.append(result)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate dev-pace JSONL logs into privacy-reduced daily records.")
    parser.add_argument("--input", type=Path, default=project_root() / "logs")
    parser.add_argument("--output", type=Path, default=project_root() / "outputs" / "activity_daily.jsonl")
    parser.add_argument("--timezone", default="Asia/Tokyo", help="Timezone used for the calendar-day and hourly buckets.")
    args = parser.parse_args()

    records = load_records(discover_logs(args.input))
    daily = aggregate(records, args.timezone)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in daily:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    print(json.dumps({"records": len(records), "days": len(daily), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
