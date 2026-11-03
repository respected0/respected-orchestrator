"""KPI report and regression gate for evaluation reports (EVAL-03)."""
from __future__ import annotations

REQUIRED_KPIS = ("acceptance_success_rate", "worker_violations", "cost", "duration_seconds")


def _summary(report):
    if not isinstance(report, dict) or report.get("schema") != "respected.eval.compare.v1":
        raise ValueError("invalid_report")
    summary = report.get("summary")
    if not isinstance(summary, dict) or not isinstance(summary.get("orchestrated"), dict):
        raise ValueError("missing_kpi")


def kpis(report):
    """Return the four product KPIs; missing data raises instead of becoming zero."""
    _summary(report)
    values = report["summary"]["orchestrated"]
    for key in ("success_rate", "security_violations", "cost", "duration_seconds"):
        if values.get(key) is None:
            raise ValueError(f"missing_kpi:{key}")
    return {
        "acceptance_success_rate": values["success_rate"],
        "worker_violations": values["security_violations"],
        "cost": values["cost"],
        "duration_seconds": values["duration_seconds"],
    }


def regression_gate(baseline, current):
    """Block when success drops or worker violations rise between two runs."""
    before = kpis(baseline)
    after = kpis(current)
    for field in ("fixture_ids", "repeat", "timeout"):
        if baseline.get(field) != current.get(field):
            raise ValueError(f"incomparable:{field}")
    regressions = []
    if after["acceptance_success_rate"] < before["acceptance_success_rate"]:
        regressions.append("acceptance_success_rate")
    if after["worker_violations"] > before["worker_violations"]:
        regressions.append("worker_violations")
    return {"ok": not regressions, "regressions": regressions, "baseline": before, "current": after}


def render_markdown(report, gate=None):
    values = kpis(report)
    lines = [
        "# Değerlendirme raporu",
        "",
        "| KPI | Değer |",
        "|---|---|",
        f"| Kabul başarısı | {values['acceptance_success_rate']} |",
        f"| Worker ihlali | {values['worker_violations']} |",
        f"| Maliyet | {values['cost']} |",
        f"| Süre (sn) | {values['duration_seconds']} |",
    ]
    if gate is not None:
        lines += ["", "## Regresyon kapısı", "", f"- Sonuç: {'geçti' if gate['ok'] else 'engellendi'}"]
        lines += [f"- Regresyon: {name}" for name in gate.get("regressions", [])]
    return "\n".join(lines) + "\n"