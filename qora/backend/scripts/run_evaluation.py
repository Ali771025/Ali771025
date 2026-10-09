"""Run deterministic intent/outcome regression suites: python scripts/run_evaluation.py"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation.harness import run_evaluation


if __name__ == "__main__":
    report = run_evaluation()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["intent"]["passed"] != report["intent"]["cases"] or report["outcome"]["passed"] != report["outcome"]["cases"]:
        raise SystemExit(1)
