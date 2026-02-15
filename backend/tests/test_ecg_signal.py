import math
import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import simulate_ecg  # noqa: E402


class EcgSignalTests(unittest.TestCase):
    @staticmethod
    def _peak_indices(signal, threshold=0.6):
        peaks = []
        for i in range(1, len(signal) - 1):
            if signal[i] > threshold and signal[i] >= signal[i - 1] and signal[i] >= signal[i + 1]:
                peaks.append(i)
        return peaks

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

    def test_severe_arrhythmia_has_higher_rr_interval_variability(self):
        normal_payload = {"age": 42, "thalach": 72, "restecg": 0, "oldpeak": 0.1, "exang": 0}
        severe_payload = {"age": 70, "thalach": 120, "restecg": 1, "oldpeak": 3.4, "exang": 1}

        normal = simulate_ecg(normal_payload, 12.0, seconds=12, out_points=1200)
        severe = simulate_ecg(severe_payload, 95.0, seconds=12, out_points=1200)

        normal_peaks = self._peak_indices(normal, threshold=0.6)
        severe_peaks = self._peak_indices(severe, threshold=0.5)

        self.assertGreaterEqual(len(normal_peaks), 5)
        self.assertGreaterEqual(len(severe_peaks), 5)

        normal_rr = [normal_peaks[i] - normal_peaks[i - 1] for i in range(1, len(normal_peaks))]
        severe_rr = [severe_peaks[i] - severe_peaks[i - 1] for i in range(1, len(severe_peaks))]

        normal_cv = (float((sum((x - (sum(normal_rr) / len(normal_rr))) ** 2 for x in normal_rr) / len(normal_rr)) ** 0.5) / (sum(normal_rr) / len(normal_rr)))
        severe_cv = (float((sum((x - (sum(severe_rr) / len(severe_rr))) ** 2 for x in severe_rr) / len(severe_rr)) ** 0.5) / (sum(severe_rr) / len(severe_rr)))

        self.assertGreater(severe_cv, normal_cv + 0.08)


if __name__ == "__main__":
    unittest.main()
