from __future__ import annotations

from pathlib import Path
import argparse
import json
from datetime import datetime
from html import escape

LOG_DIR_NAME = "logs"

CATEGORY_COLORS = {
    "AI": "#2563eb",
    "Web AI": "#0891b2",
    "開発": "#0f766e",
    "ノート": "#10b981",
    "文書作成": "#f97316",
    "YouTube": "#ef4444",
    "検索": "#f59e0b",
    "技術系Web": "#8b5cf6",
    "一般Web": "#64748b",
    "システム": "#84cc16",
}

AI_COLORS = {
    "Claude": "#4f46e5",
    "ChatGPT": "#10b981",
    "Gemini": "#06b6d4",
    "Perplexity": "#f59e0b",
}

DEV_COLORS = {
    "VS Code": "#007acc",
    "Codex": "#111827",
    "GitHub": "#24292e",
    "ターミナル": "#16a34a",
}


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def log_dirs() -> list[Path]:
    root = project_root()
    return [root / LOG_DIR_NAME]


def output_path() -> Path:
    return Path.cwd().resolve() / "outputs" / "activity_dashboard.html"


def discover_log_files() -> list[Path]:
    found = {}
    for root in log_dirs():
        if not root.exists():
            continue
        for path in root.glob("activity_*.jsonl"):
            try:
                resolved = path.resolve()
                found[resolved] = path
            except Exception:
                continue
    return sorted(found.values(), key=lambda p: p.stat().st_mtime, reverse=True)


def load_records(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                obj["_line"] = lineno
                records.append(obj)
    return records


def format_timestamp(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return value


def contains_any(text: str, needles: list[str]) -> bool:
    return any(n in text for n in needles)


def classify_window(title: str) -> str:
    text = str(title)
    lower = text.lower()
    if "[web-ai:" in lower:
        return "Web AI"
    browser = contains_any(text, ["Google Chrome", "Microsoft Edge", "Mozilla Firefox", "Brave"])
    web_ai = contains_any(text, [
        "Claude - ", "ChatGPT - ", "Google Gemini", "Gemini - ",
        "Perplexity - ", "Microsoft Copilot", "Copilot - ",
    ])
    if browser and web_ai:
        return "Web AI"
    if not browser and contains_any(text, ["Claude", "ChatGPT", "Gemini", "Perplexity", "Copilot", "Anthropic", "OpenAI"]):
        return "AI"
    if contains_any(text, ["Visual Studio Code", "VS Code", "Codex", "Windows PowerShell", "PowerShell", "Windows Terminal", "Terminal", "cmd", "GitHub Desktop"]):
        return "開発"
    if contains_any(text, ["Obsidian", "Notion", "Evernote", "OneNote", "Joplin", "Bear"]):
        return "ノート"
    if contains_any(text, ["Word", "Excel", "PowerPoint", "LibreOffice", "Docs", "Sheets", "Slides", "Google ドキュメント", "Google スプレッドシート", "Google スライド"]):
        return "文書作成"
    if "youtube" in lower:
        return "YouTube"
    if contains_any(text, ["Google 検索", "Bing", "DuckDuckGo", "Search", "検索"]):
        return "検索"
    if contains_any(text, ["GitHub", "Qiita", "Zenn", "Stack Overflow", "MDN", "developer", "docs", "npm", "crates", "rust", "readthedocs"]):
        return "技術系Web"
    if contains_any(text, ["Explorer", "エクスプローラー", "設定", "Settings", "Task Manager", "タスク マネージャー", "PowerToys"]):
        return "システム"
    return "一般Web"


def classify_ai_detail(title: str) -> str:
    text = str(title)
    if "Claude" in text:
        return "Claude"
    if "ChatGPT" in text:
        return "ChatGPT"
    if "Gemini" in text:
        return "Gemini"
    if "Perplexity" in text:
        return "Perplexity"
    return "その他"


def classify_dev_detail(title: str) -> str:
    text = str(title)
    if contains_any(text, ["Visual Studio Code", "VS Code", "Code -"]):
        return "VS Code"
    if "Codex" in text:
        return "Codex"
    if contains_any(text, ["GitHub", "github"]):
        return "GitHub"
    if contains_any(text, ["Terminal", "PowerShell", "cmd", "Windows Terminal"]):
        return "ターミナル"
    return "その他"


def add_count(bucket: dict[str, float], key: str, value: float) -> None:
    bucket[key] = bucket.get(key, 0.0) + float(value)


def summarize_records(records: list[dict]) -> dict:
    overall = {k: 0.0 for k in CATEGORY_COLORS}
    ai = {k: 0.0 for k in AI_COLORS}
    dev = {k: 0.0 for k in DEV_COLORS}
    state_counts: dict[str, int] = {}
    total_minutes = len(records)
    total_ops = 0
    recent = []

    for rec in records:
        title = str(rec.get("main_window") or rec.get("window") or "Unknown")
        state = str(rec.get("state", "Unknown"))
        ops = int(rec.get("ops", 0) or 0)
        total_ops += ops
        state_counts[state] = state_counts.get(state, 0) + 1

        recent.append({
            "timestamp": rec.get("timestamp", ""),
            "main_window": title,
            "state": state,
            "ops": ops,
        })

        distribution = rec.get("distribution")
        if isinstance(distribution, dict) and distribution:
            for raw_title, value in distribution.items():
                window = str(raw_title)
                weight = float(value) / 60.0
                category = classify_window(window)
                add_count(overall, category, weight)
                if category in ("AI", "Web AI"):
                    add_count(ai, classify_ai_detail(window), weight)
                if category == "開発":
                    add_count(dev, classify_dev_detail(window), weight)
        else:
            category = classify_window(title)
            add_count(overall, category, 1.0)
            if category in ("AI", "Web AI"):
                add_count(ai, classify_ai_detail(title), 1.0)
            if category == "開発":
                add_count(dev, classify_dev_detail(title), 1.0)

    return {
        "overall": overall,
        "ai": ai,
        "dev": dev,
        "state_counts": state_counts,
        "total_ops": total_ops,
        "count": total_minutes,
        "recent": recent[-24:],
    }


def pct(value: float, total: float) -> float:
    return 0.0 if total <= 0 else round((value / total) * 100, 1)


def gradient(items: list[tuple[str, float]], palette: dict[str, str]) -> str:
    total = sum(v for _, v in items)
    if total <= 0:
        return "conic-gradient(#e2e8f0 0 100%)"
    cursor = 0.0
    parts = []
    for label, value in items:
        if value <= 0:
            continue
        next_cursor = cursor + (value / total) * 100
        parts.append(f"{palette.get(label, '#94a3b8')} {cursor:.3f}% {next_cursor:.3f}%")
        cursor = next_cursor
    return "conic-gradient(" + ", ".join(parts) + ")"


def legend_html(items: list[tuple[str, float]], palette: dict[str, str], total: float) -> str:
    rows = []
    for label, value in items:
        if value <= 0:
            continue
        rows.append(f"""
        <div class="legend-row">
          <div class="legend-left">
            <span class="swatch" style="background:{palette.get(label, '#94a3b8')}"></span>
            <span class="legend-label">{escape(label)}</span>
          </div>
          <div class="legend-right">{pct(value, total):.1f}%</div>
        </div>
        """)
    return "\n".join(rows) if rows else '<div class="empty">データなし</div>'


def donut_card(title: str, subtitle: str, items: list[tuple[str, float]], palette: dict[str, str], total: float, center_label: str) -> str:
    return f"""
    <section class="card">
      <div class="card-head">
        <div>
          <h2>{escape(title)}</h2>
          <p>{escape(subtitle)}</p>
        </div>
      </div>
      <div class="donut-wrap">
        <div class="donut" style="background:{gradient(items, palette)}">
          <div class="donut-hole">
            <div class="donut-value">{escape(center_label)}</div>
            <div class="donut-sub">合計</div>
          </div>
        </div>
        <div class="legend">{legend_html(items, palette, total)}</div>
      </div>
    </section>
    """


def render_day_page(log_file: Path, summary: dict) -> str:
    overall_order = ["AI", "Web AI", "開発", "ノート", "文書作成", "YouTube", "検索", "技術系Web", "一般Web", "システム"]
    ai_order = ["Claude", "ChatGPT", "Gemini", "Perplexity"]
    dev_order = ["VS Code", "Codex", "GitHub", "ターミナル"]

    overall_items = [(k, summary["overall"].get(k, 0.0)) for k in overall_order]
    ai_items = [(k, summary["ai"].get(k, 0.0)) for k in ai_order]
    dev_items = [(k, summary["dev"].get(k, 0.0)) for k in dev_order]

    top_category = max(overall_items, key=lambda kv: kv[1])[0] if summary["count"] else "-"
    top_state = max(summary["state_counts"].items(), key=lambda kv: kv[1])[0] if summary["state_counts"] else "-"

    state_rows = []
    state_total = max(1, len(summary["recent"]))
    for label, value in sorted(summary["state_counts"].items(), key=lambda kv: kv[1], reverse=True):
        state_rows.append(f"""
        <div class="bar-row">
          <div class="bar-label">{escape(label)}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{min(100, value * 100 / state_total):.1f}%"></div></div>
          <div class="bar-value">{value}</div>
        </div>
        """)
    state_html = "\n".join(state_rows) if state_rows else '<div class="empty">データなし</div>'

    recent_rows = []
    for rec in reversed(summary["recent"]):
        recent_rows.append(f"""
        <tr>
          <td>{escape(format_timestamp(str(rec.get('timestamp', ''))))}</td>
          <td><span class="state-pill">{escape(str(rec.get('state', '')))}</span></td>
          <td class="num">{escape(str(rec.get('ops', 0)))}</td>
          <td>{escape(str(rec.get('main_window', '')))}</td>
        </tr>
        """)
    recent_html = "\n".join(recent_rows) if recent_rows else '<tr><td colspan="4" class="empty">データなし</td></tr>'

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Activity Dashboard</title>
  <style>
    :root {{
      --bg: #f4f7fb;
      --panel: rgba(255,255,255,.95);
      --panel-border: rgba(15,23,42,.08);
      --text: #0f172a;
      --muted: #64748b;
      --shadow: 0 18px 50px rgba(15,23,42,.08);
      --radius: 18px;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Hiragino Kaku Gothic ProN", "Yu Gothic UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at top left, rgba(37,99,235,.08), transparent 36%),
        radial-gradient(circle at top right, rgba(16,185,129,.10), transparent 34%),
        linear-gradient(180deg, #fbfdff 0%, var(--bg) 100%);
    }}
    .page {{ max-width: 1500px; margin: 0 auto; padding: 24px; }}
    .hero {{
      background: linear-gradient(135deg, rgba(15,23,42,.96), rgba(30,41,59,.94));
      color: white;
      border-radius: 28px;
      padding: 26px 28px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }}
    .hero-top {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: start;
      flex-wrap: wrap;
    }}
    .hero h1 {{ margin: 0 0 10px; font-size: 30px; line-height: 1.1; }}
    .hero p, .meta {{ margin: 0; color: rgba(255,255,255,.78); font-size: 14px; line-height: 1.5; }}
    .chips {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }}
    .chip {{
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255,255,255,.08);
      border: 1px solid rgba(255,255,255,.10);
      font-size: 13px;
    }}
    .layout {{ display: grid; grid-template-columns: 320px 1fr; gap: 18px; align-items: start; }}
    .sidebar, .main {{ display: grid; gap: 18px; }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--panel-border);
      box-shadow: var(--shadow);
      border-radius: var(--radius);
      padding: 18px;
      overflow: hidden;
    }}
    .card-head h2 {{ margin: 0; font-size: 18px; }}
    .card-head p {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; }}
    .file-list {{ display: grid; gap: 8px; margin-top: 14px; }}
    .file-btn {{
      display: flex; justify-content: space-between; gap: 12px; width: 100%;
      border: 1px solid rgba(15,23,42,.08); background: white; padding: 12px 14px;
      border-radius: 14px; cursor: pointer; text-align: left; font: inherit;
    }}
    .file-btn.active {{ border-color: rgba(37,99,235,.28); background: rgba(37,99,235,.06); }}
    .file-btn .name {{ font-weight: 700; }}
    .file-btn .date {{ color: var(--muted); font-size: 12px; white-space: nowrap; }}
    .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px; }}
    .stat {{
      background: var(--panel); border: 1px solid var(--panel-border); box-shadow: var(--shadow);
      border-radius: var(--radius); padding: 18px;
    }}
    .stat .label {{ color: var(--muted); font-size: 13px; margin-bottom: 8px; }}
    .stat .value {{ font-size: 28px; font-weight: 700; }}
    .donut-wrap {{ display: grid; grid-template-columns: 300px 1fr; gap: 18px; align-items: center; margin-top: 14px; }}
    .donut {{ width: 280px; aspect-ratio: 1; border-radius: 50%; position: relative; margin: 0 auto; }}
    .donut::after {{ content: ""; position: absolute; inset: 22%; background: white; border-radius: 50%; }}
    .donut-hole {{
      position: absolute; inset: 22%; z-index: 1; display: flex; flex-direction: column;
      align-items: center; justify-content: center; text-align: center; padding: 12px;
    }}
    .donut-value {{ font-size: 26px; font-weight: 800; line-height: 1.1; }}
    .donut-sub {{ color: var(--muted); margin-top: 4px; font-size: 13px; }}
    .legend {{ display: grid; gap: 10px; }}
    .legend-row {{
      display: flex; justify-content: space-between; align-items: center; gap: 12px;
      padding: 10px 12px; border: 1px solid rgba(15,23,42,.08); border-radius: 14px;
      background: rgba(255,255,255,.72);
    }}
    .legend-left {{ display: flex; align-items: center; gap: 10px; min-width: 0; }}
    .legend-label {{ font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .legend-right {{ color: var(--muted); font-variant-numeric: tabular-nums; flex: 0 0 auto; }}
    .swatch {{ width: 14px; height: 14px; border-radius: 999px; flex: 0 0 auto; }}
    .bars {{ display: grid; gap: 10px; margin-top: 14px; }}
    .bar-row {{ display: grid; grid-template-columns: 110px 1fr 42px; gap: 10px; align-items: center; }}
    .bar-label {{ font-weight: 600; font-size: 14px; }}
    .bar-track {{ height: 10px; background: rgba(148,163,184,.18); border-radius: 999px; overflow: hidden; }}
    .bar-fill {{ height: 100%; background: linear-gradient(90deg, #2563eb, #0ea5e9); border-radius: 999px; }}
    .bar-value {{ text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; }}
    .table-wrap {{ margin-top: 14px; overflow: hidden; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    thead th {{
      text-align: left; padding: 12px 10px; color: var(--muted); font-weight: 600;
      border-bottom: 1px solid rgba(15,23,42,.08);
    }}
    tbody td {{ padding: 11px 10px; border-bottom: 1px solid rgba(15,23,42,.06); vertical-align: top; }}
    .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .state-pill {{
      display: inline-flex; padding: 5px 10px; border-radius: 999px; background: rgba(37,99,235,.10);
      color: #1d4ed8; font-size: 12px; font-weight: 700;
    }}
    .empty {{ color: var(--muted); padding: 12px 0; }}
    @media (max-width: 1200px) {{
      .layout, .donut-wrap, .stats {{ grid-template-columns: 1fr; }}
      .donut {{ width: min(84vw, 280px); }}
    }}
    @media (max-width: 760px) {{
      .page {{ padding: 14px; }}
      .hero {{ border-radius: 22px; padding: 20px; }}
      .hero h1 {{ font-size: 26px; }}
      .bar-row {{ grid-template-columns: 92px 1fr 36px; }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1>Activity Dashboard</h1>
          <p>JSONL を日付ごとに切り替えて見られるダッシュボードです。</p>
        </div>
        <div class="meta">
          <div>Source: {escape(str(log_file))}</div>
          <div>Generated: {escape(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))}</div>
        </div>
      </div>
      <div class="chips">
        <span class="chip">全体利用割合</span>
        <span class="chip">AI内訳</span>
        <span class="chip">開発内訳</span>
        <span class="chip">日付別表示</span>
      </div>
    </section>

    <div class="layout">
      <main class="main">
        <section class="stats">
          <div class="stat"><div class="label">使用分</div><div class="value">{summary['count']}</div></div>
          <div class="stat"><div class="label">Ops</div><div class="value">{summary['total_ops']}</div></div>
          <div class="stat"><div class="label">Top category</div><div class="value">{escape(top_category)}</div></div>
          <div class="stat"><div class="label">Top state</div><div class="value">{escape(top_state)}</div></div>
        </section>

        {donut_card("全体利用割合", "AI / 開発 / ノート / 文書作成 / YouTube / 検索 / 技術系Web / 一般Web / システム", overall_items, CATEGORY_COLORS, sum(summary["overall"].values()), f"{sum(summary['overall'].values()):.0f}")}
        {donut_card("AI内訳", "Claude / ChatGPT / Gemini / Perplexity", ai_items, AI_COLORS, sum(summary["ai"].values()), f"{sum(summary['ai'].values()):.0f}")}
        {donut_card("開発内訳", "VS Code / Codex / GitHub / ターミナル", dev_items, DEV_COLORS, sum(summary["dev"].values()), f"{sum(summary['dev'].values()):.0f}")}

        <section class="card">
          <div class="card-head">
            <h2>State Summary</h2>
            <p>状態ごとの出現回数</p>
          </div>
          <div class="bars">{state_html}</div>
        </section>

        <section class="card">
          <div class="card-head">
              <h2>Recent Records</h2>
            <p>最後の 24 件</p>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>State</th>
                  <th class="num">Ops</th>
                  <th>Main window</th>
                </tr>
              </thead>
              <tbody>{recent_html}</tbody>
            </table>
          </div>
        </section>
      </main>
    </div>
  </div>
</body>
</html>
"""


def render_index(log_files: list[Path]) -> str:
    if not log_files:
        return """<!doctype html>
<html lang="ja">
<head><meta charset="utf-8"><title>Activity Dashboard</title></head>
<body style="font-family:Segoe UI,sans-serif;padding:24px"><h1>No logs</h1><p>logs フォルダに activity_*.jsonl がありません。</p></body>
</html>"""

    pages = []
    buttons = []
    metas = []
    for i, path in enumerate(log_files):
        try:
            summary = summarize_records(load_records(path))
        except Exception:
            continue
        pages.append(render_day_page(path, summary))
        metas.append({
            "date": path.stem.replace("activity_", ""),
            "path": str(path),
             "minutes": summary["count"],
             "ops": summary["total_ops"],
         })
        button_label = path.stem.replace("activity_", "")
        buttons.append(
            f'<button class="file-btn {"active" if i == 0 else ""}" data-index="{i}"><span class="name">{escape(button_label)}</span><span class="date">{escape(path.name)}</span></button>'
        )

    pages_json = json.dumps(pages, ensure_ascii=False).replace("</", "<\\/")
    metas_json = json.dumps(metas, ensure_ascii=False).replace("</", "<\\/")
    first = pages[0]

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Activity Dashboard</title>
  <style>
    body {{ margin: 0; background: #eef2f7; font-family: "Segoe UI", "Hiragino Kaku Gothic ProN", "Yu Gothic UI", sans-serif; }}
    .frame {{ display: grid; grid-template-columns: 320px 1fr; min-height: 100vh; }}
    .nav {{ background: #fff; border-right: 1px solid rgba(15,23,42,.08); padding: 18px; overflow: auto; }}
    .viewer {{ background: #eef2f7; overflow: auto; }}
    .title {{ font-size: 20px; font-weight: 800; margin: 0 0 8px; }}
    .sub {{ color: #64748b; font-size: 13px; margin-bottom: 14px; }}
    .file-list {{ display: grid; gap: 8px; }}
    .file-btn {{ display: flex; justify-content: space-between; gap: 12px; width: 100%; border: 1px solid rgba(15,23,42,.08); background: #fff; padding: 12px 14px; border-radius: 14px; cursor: pointer; text-align: left; font: inherit; }}
    .file-btn.active {{ background: rgba(37,99,235,.06); border-color: rgba(37,99,235,.28); }}
    .file-btn .name {{ font-weight: 700; }}
    .file-btn .date {{ color: #64748b; font-size: 12px; white-space: nowrap; }}
    .viewer iframe {{ width: 100%; height: 100vh; border: 0; }}
    @media (max-width: 960px) {{
      .frame {{ grid-template-columns: 1fr; }}
      .viewer iframe {{ height: 72vh; }}
    }}
  </style>
</head>
<body>
  <div class="frame">
    <aside class="nav">
      <div class="title">Activity Dashboard</div>
      <div class="sub">日付を選ぶと、その日の集計に切り替わります。</div>
      <div id="meta" class="sub"></div>
      <div class="file-list">{''.join(buttons)}</div>
    </aside>
    <main class="viewer">
      <iframe id="viewer" srcdoc='{escape(first, quote=True)}'></iframe>
    </main>
  </div>
  <script>
    const pages = {pages_json};
    const metas = {metas_json};
    const viewer = document.getElementById('viewer');
    const metaBox = document.getElementById('meta');
    const buttons = Array.from(document.querySelectorAll('.file-btn'));
    function activate(index) {{
      viewer.srcdoc = pages[index];
      buttons.forEach((btn, i) => btn.classList.toggle('active', i === index));
      const m = metas[index];
      metaBox.textContent = `${{m.date}} / minutes: ${{m.minutes}} / ops: ${{m.ops}}`;
    }}
    buttons.forEach((btn, i) => btn.addEventListener('click', () => activate(i)));
    activate(0);
  </script>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=output_path())
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    html = render_index(discover_log_files())
    args.output.write_text(html, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
