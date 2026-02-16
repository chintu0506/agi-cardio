import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from safety_gate_calibration_suite import CALIBRATION_CASES, run_calibration_suite  # noqa: E402


class SafetyGateCalibrationTests(unittest.TestCase):
    def test_case_pack_has_expected_size(self):
        self.assertGreaterEqual(len(CALIBRATION_CASES), 20)

    def test_calibration_suite_passes(self):
        report = run_calibration_suite()
        failed_rows = [row for row in report.get("cases", []) if not row.get("all_checks_passed")]
        details = "; ".join(
            f"{row.get('id')} -> {', '.join(row.get('failed_checks', []))}"
            for row in failed_rows[:8]
        )
        self.assertEqual(
            int(report.get("summary", {}).get("failed_cases", 0)),
            0,
            msg=f"Calibration suite has failures: {details}",
        )


if __name__ == "__main__":
    unittest.main()
