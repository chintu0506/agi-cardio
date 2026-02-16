import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from safety_gate_calibration_suite import run_calibration_suite  # noqa: E402


def _format_report_md(report):
    summary = report.get("summary") or {}
    categories = report.get("categories") or {}
    cases = report.get("cases") or []
    lines = []
    lines.append("# Safety Gate Calibration Report")
    lines.append("")
    lines.append(f"- Generated At (UTC): `{report.get('generated_at', '')}`")
    lines.append(f"- Master Threshold: `{report.get('master_threshold_pct', 0.0):.1f}%`")
    lines.append(f"- Total Cases: `{summary.get('total_cases', 0)}`")
    lines.append(f"- Passed Cases: `{summary.get('passed_cases', 0)}`")
    lines.append(f"- Failed Cases: `{summary.get('failed_cases', 0)}`")
    lines.append(f"- Pass Rate: `{summary.get('pass_rate_pct', 0.0):.1f}%`")
    lines.append("")
    lines.append("## Acceptance Targets")
    lines.append("")
    lines.append("- Baseline cases: `status=ok`, `confidence>=70`, `boundary>15%`, `OOD=0`.")
    lines.append("- Mild-risk cases: `25%<=risk<40%`, `status=ok`, `confidence>=70`, `OOD=0`.")
    lines.append("- True-abnormal cases: `status in {caution, blocked}` with biomarker trigger.")
    lines.append("")
    lines.append("## Category Summary")
    lines.append("")
    lines.append("| Category | Cases | Passed | Failed | Pass Rate |")
    lines.append("|---|---:|---:|---:|---:|")
    for category in sorted(categories.keys()):
        bucket = categories.get(category) or {}
        lines.append(
            f"| {category} | {int(bucket.get('total', 0))} | {int(bucket.get('passed', 0))} | "
            f"{int(bucket.get('failed', 0))} | {float(bucket.get('pass_rate_pct', 0.0)):.1f}% |"
        )
    lines.append("")
    lines.append("## Case Results")
    lines.append("")
    lines.append("| Case | Category | Risk | Status | Confidence | Boundary | OOD | Triggers | Pass | Failed Checks |")
    lines.append("|---|---|---:|---|---:|---:|---:|---|---|---|")
    for row in cases:
        metrics = row.get("metrics") or {}
        triggers = metrics.get("trigger_flags") or {}
        trigger_text = ",".join([k for k, v in triggers.items() if v]) or "none"
        failed_checks = ", ".join(row.get("failed_checks") or []) or "-"
        lines.append(
            f"| {row.get('id','')} | {row.get('category','')} | {float(metrics.get('risk', 0.0)):.1f}% | "
            f"{metrics.get('status','')} | {float(metrics.get('confidence_score', 0.0)):.1f} | "
            f"{float(metrics.get('boundary_distance_pct', 0.0)):.1f}% | {int(metrics.get('ood_feature_count', 0))} | "
            f"{trigger_text} | {'PASS' if row.get('all_checks_passed') else 'FAIL'} | {failed_checks} |"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    report = run_calibration_suite()
    report_dir = TESTS_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    md_path = report_dir / "safety_gate_calibration_report.md"
    json_path = report_dir / "safety_gate_calibration_report.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    md_path.write_text(_format_report_md(report), encoding="utf-8")

    summary = report.get("summary") or {}
    failed = int(summary.get("failed_cases", 0))
    print(f"Generated report: {md_path}")
    print(f"Generated report: {json_path}")
    print(
        f"Calibration result: {int(summary.get('passed_cases', 0))}/{int(summary.get('total_cases', 0))} "
        f"cases passed ({float(summary.get('pass_rate_pct', 0.0)):.1f}%)."
    )
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
