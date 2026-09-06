"""V2.0 Evaluation Analysis and Report Generator.

Reads experiment results JSON and produces a structured Markdown report.

Usage:
    python -m experiments.voice.v2_0_analysis
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))


def load_results(results_path: Path) -> dict:
    with open(results_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_report(results: dict) -> str:
    lines = []
    lines.append("# V2.0 Evaluation Results")
    lines.append("")
    lines.append(f"**Experiment:** {results['experiment_id']}")
    lines.append(f"**Timestamp:** {results['timestamp']}")
    lines.append(f"**Git commit:** {results['config'].get('git_commit', 'unknown')}")
    lines.append(f"**Errors:** {results.get('errors_count', len(results.get('errors', [])))}")
    lines.append("")

    # Summary metrics
    lines.append("## Summary Metrics")
    lines.append("")
    lines.append("| Metric | Count | Mean | Min | Max |")
    lines.append("|--------|------:|-----:|----:|----:|")
    for name, stats in results.get("summary", {}).items():
        lines.append(
            f"| {name} | {stats['count']} | {stats['mean']} "
            f"| {stats['min']} | {stats['max']} |"
        )
    lines.append("")

    # Detailed metrics
    lines.append("## Detailed Metrics")
    lines.append("")
    for m in results.get("metrics", []):
        lines.append(f"- **{m['metric_name']}**: {json.dumps(m)}")
    lines.append("")

    # Evaluation matrix
    lines.append("## Evaluation Matrix")
    lines.append("")
    speakers = results["config"].get("speakers", [])
    header = "| Test | " + " | ".join(speakers) + " |"
    sep = "|------|" + "|".join(["---"] * len(speakers)) + "|"
    lines.append(header)
    lines.append(sep)

    # Build matrix from metrics
    consistency = {}
    retention = {}
    for m in results.get("metrics", []):
        if m["metric_name"] == "representation_consistency":
            sid = m.get("speaker_id", "?")
            consistency.setdefault(sid, []).append(m["similarity"])
        elif m["metric_name"] == "generated_identity_retention":
            sid = m.get("speaker_id", "?")
            retention.setdefault(sid, []).append(m["similarity"])

    def fmt(vals):
        if not vals:
            return "N/A"
        avg = sum(vals) / len(vals)
        return f"{avg:.4f} (n={len(vals)})"

    lines.append(f"| Representation consistency | " +
                 " | ".join(fmt(consistency.get(s, [])) for s in speakers) + " |")
    lines.append(f"| Generated identity retention | " +
                 " | ".join(fmt(retention.get(s, [])) for s in speakers) + " |")
    lines.append("")

    # Errors
    if results.get("errors"):
        lines.append("## Errors")
        lines.append("")
        for err in results["errors"]:
            lines.append(f"- {err}")
        lines.append("")

    return "\n".join(lines)


def main():
    output_dir = project_root / "data" / "evaluation" / "output"
    results_files = sorted(output_dir.glob("*_results.json"))

    if not results_files:
        print("No results found. Run v2_0_eval.py first.")
        sys.exit(1)

    latest = results_files[-1]
    print(f"Loading: {latest}")
    results = load_results(latest)
    report = generate_report(results)

    report_path = project_root / "docs" / "evaluation" / "v2_0_results.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written to: {report_path}")
    print()
    print(report)


if __name__ == "__main__":
    main()
