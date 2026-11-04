import json
import os
import pandas as pd


def export_all_artifacts(
    topic: str,
    df: pd.DataFrame,
    narratives: list[dict],
    coord_groups: list[dict],
    origins: list[dict],
    out_dir: str = "output",
) -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "posts.csv")
    json_path = os.path.join(out_dir, "intelligence_report.json")
    html_path = os.path.join(out_dir, "report.html")

    # 1. Save CSV
    export_df = df.drop(columns=["timestamp_dt", "author_created_dt"], errors="ignore")
    export_df.to_csv(csv_path, index=False)

    # 2. Save JSON
    payload = {
        "topic": topic,
        "total_posts": len(export_df),
        "narratives": narratives,
        "coordinated_groups": coord_groups,
        "narrative_origins": origins,
        "posts": export_df.to_dict("records"),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    # 3. Build HTML Table Rows
    narrative_rows = "".join(
        [
            f"<tr><td><b>{n['narrative_label']}</b></td>"
            f"<td>{n['post_count']}</td>"
            f"<td>{n['platforms']}</td>"
            f"<td>{n['representative_claim']}</td>"
            f"<td><span style='color:#4ade80'>{n['ai_grounding_check']}</span></td></tr>"
            for n in narratives
        ]
    )

    coord_rows = "".join(
        [
            f"<tr><td><b>{g['group_id']}</b><br><span style='color:#f87171'>Confidence: {g['confidence_score']}</span></td>"
            f"<td>{', '.join(g['accounts'])}</td>"
            f"<td>{', '.join(g['platforms'])}</td>"
            f"<td><ul>{''.join(f'<li>{r}</li>' for r in g['reasons'][:8])}</ul></td></tr>"
            for g in coord_groups
        ]
    )

    origin_rows = "".join(
        [
            f"<tr><td><b>{o['narrative_label']}</b></td>"
            f"<td>{o['origin_platform']} ({o['origin_account']})</td>"
            f"<td>{o['origin_timestamp']}</td>"
            f"<td>{o['cross_platform_spread']}</td>"
            f"<td><a href='{o['origin_link']}' target='_blank'>{o['origin_text'][:80]}...</a></td></tr>"
            for o in origins
        ]
    )
    html_content = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>SOCMINT & Disinformation Report - {topic}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background: #0f172a; color: #f8fafc; padding: 28px; line-height: 1.5; }}
  h1, h2 {{ color: #38bdf8; border-bottom: 1px solid #334155; padding-bottom: 6px; }}
  .kpi-box {{ display: flex; gap: 20px; margin-bottom: 24px; }}
  .kpi {{ background: #1e293b; border: 1px solid #334155; padding: 14px 20px; border-radius: 8px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; background: #1e293b; font-size: 14px; }}
  th, td {{ border: 1px solid #334155; padding: 10px; text-align: left; vertical-align: top; }}
  th {{ background: #0284c7; color: white; }}
  a {{ color: #7dd3fc; }}
  ul {{ margin: 0; padding-left: 18px; }}
</style>
</head>
<body>
  <h1>SOCMINT & Coordinated Disinformation Report: {topic}</h1>
  <div class="kpi-box">
    <div class="kpi">Total Posts Analyzed: <b>{len(export_df)}</b></div>
    <div class="kpi">Narratives Detected: <b>{len(narratives)}</b></div>
    <div class="kpi">Coordinated Bot Rings: <b>{len(coord_groups)}</b></div>
  </div>

  <h2>1. Main Narratives & Volume Breakdown</h2>
  <table>
    <tr><th>Narrative</th><th>Posts</th><th>Platform Split</th><th>Representative Claim</th><th>AI Grounding Check</th></tr>
    {narrative_rows}
  </table>

  <h2>2. Coordinated Account Groups & Detection Evidence</h2>
  <table>
    <tr><th>Group ID & Confidence</th><th>Accounts Involved</th><th>Platforms</th><th>Detected Coordination Signals</th></tr>
    {coord_rows}
  </table>

  <h2>3. Narrative Origin ('Patient Zero') & Cross-Platform Propagation</h2>
  <table>
    <tr><th>Narrative</th><th>Patient Zero</th><th>First Seen (UTC)</th><th>Propagation Chain</th><th>Initial Post</th></tr>
    {origin_rows}
  </table>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return {"csv": csv_path, "json": json_path, "html": html_path}
