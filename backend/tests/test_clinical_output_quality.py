import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import DEFAULT_PATIENT, generate_diagnosis  # noqa: E402


class ClinicalOutputQualityTests(unittest.TestCase):
    def test_recommendations_do_not_mix_urgent_with_routine_checkup(self):
        critical = {
            "age": 68,
            "sex": 1,
            "cp": 3,
            "trestbps": 168,
            "chol": 295,
            "fbs": 1,
            "restecg": 1,
            "thalach": 98,
            "exang": 1,
            "oldpeak": 4.2,
            "slope": 2,
            "ca": 3,
            "thal": 3,
            "bmi": 31.2,
            "smoking": 1,
            "diabetes": 1,
            "family_history": 1,
            "creatinine": 1.4,
            "bnp": 620,
            "troponin": 1.2,
            "ejection_fraction": 32,
        }
        out = generate_diagnosis(critical)
        recs = out.get("recommendations", [])
        self.assertTrue(any(str(r.get("priority")) in ("URGENT", "HIGH") for r in recs))
        self.assertFalse(
            any("routine cardiac check-up" in str(r.get("text", "")).lower() for r in recs),
            "Routine check-up recommendation should not appear with urgent/high recommendations.",
        )

    def test_diseases_include_condition_confidence_disclaimer(self):
        out = generate_diagnosis(dict(DEFAULT_PATIENT))
        for d in out.get("diseases", []):
            disclaimer = str(d.get("confidence_disclaimer", "")).strip()
            self.assertTrue(disclaimer, f"Missing confidence disclaimer for disease: {d.get('id')}")
            self.assertGreater(len(disclaimer), 25)

    def test_rule_based_diseases_have_surrogate_disclaimer(self):
        pattern_case = {
            "age": 72,
            "sex": 0,
            "cp": 2,
            "trestbps": 155,
            "chol": 218,
            "fbs": 1,
            "restecg": 1,
            "thalach": 108,
            "exang": 0,
            "oldpeak": 1.5,
            "slope": 1,
            "ca": 1,
            "thal": 1,
            "bmi": 33.1,
            "smoking": 0,
            "diabetes": 1,
            "family_history": 1,
            "creatinine": 1.8,
            "bnp": 850,
            "troponin": 0.08,
            "ejection_fraction": 38,
        }
        out = generate_diagnosis(pattern_case)
        surrogate_cards = [d for d in out.get("diseases", []) if d.get("evidence_mode") == "rule-based-surrogate"]
        self.assertTrue(surrogate_cards)
        for d in surrogate_cards:
            disclaimer = str(d.get("confidence_disclaimer", "")).lower()
            self.assertIn("surrogate confidence", disclaimer)


if __name__ == "__main__":
    unittest.main()
