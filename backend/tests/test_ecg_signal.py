import math
import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import simulate_ecg  # noqa: E402


class EcgSignalTests(unittest.TestCase):
    def test_default_signal_shape_and_length(self):
        signal = simulate_ecg({"age": 56, "thalach": 132, "restecg": 1}, 82)
        self.assertEqual(len(signal), 300)
        self.assertTrue(all(math.isfinite(v) for v in signal))
        self.assertGreater(max(signal) - min(signal), 0.5)

    def test_signal_is_deterministic_for_same_inputs(self):
        payload = {"age": 68, "thalach": 98, "restecg": 1, "oldpeak": 4.2, "exang": 1}
        a = simulate_ecg(payload, 99.0, seconds=8, out_points=500)
        b = simulate_ecg(payload, 99.0, seconds=8, out_points=500)
        self.assertEqual(a, b)

    def test_endpoint_style_parameters_change_output_density(self):
        payload = {"age": 38, "thalach": 172, "restecg": 0}
        short = simulate_ecg(payload, 10.0, seconds=4, out_points=240)
        long = simulate_ecg(payload, 10.0, seconds=10, out_points=900)
        self.assertEqual(len(short), 240)
        self.assertEqual(len(long), 900)
        self.assertNotEqual(short[:20], long[:20])


if __name__ == "__main__":
    unittest.main()
