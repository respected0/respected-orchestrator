import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tests.evals import compare, runner, report

report_data = compare.compare(repeat=3)
out = Path("docs/ilerleme/poc/eval02_results.json")
runner.write_report(report_data, out)
gate = report.regression_gate(report_data, report_data)
Path("docs/ilerleme/poc/eval03_report.md").write_text(
    report.render_markdown(report_data, gate), encoding="utf-8", newline="\n")
Path("docs/ilerleme/poc/eval03_report.json").write_text(
    json.dumps({"kpis": report.kpis(report_data), "gate": gate}, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8", newline="\n")
print(json.dumps(report_data["summary"], ensure_ascii=False, indent=2))
print("gate", gate["ok"])