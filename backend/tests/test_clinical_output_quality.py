import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import (  # noqa: E402
    DEFAULT_PATIENT,
    assess_prediction_safety,
    calibrate_master_risk,
    compute_clinical_severity_pct,
    generate_diagnosis,
)


class ClinicalOutputQualityTests(unittest.TestCase):
    def test_low_risk_normal_biomarkers_remain_clear_with_close_classes(self):
        patient_data = {
            "age": 52,
            "sex": 1,
            "cp": 2,
            "trestbps": 126,
            "chol": 202,
            "fbs": 0,
            "restecg": 0,
            "thalach": 158,
            "exang": 0,
            "oldpeak": 0.6,
            "slope": 1,
            "ca": 0,
            "thal": 1,
            "bmi": 25.8,
            "smoking": 0,
            "diabetes": 0,
            "family_history": 0,
            "creatinine": 1.0,
            "bnp": 50,
            "troponin": 0.01,
            "ejection_fraction": 62,
        }
        probs = {"cad": 28.0, "hf": 24.0, "arr": 22.0, "mi": 15.0}
        safety = assess_prediction_safety(
            patient_data,
            probs,
            raw_master_pct=1.0,
            calibrated_master_pct=18.0,
            clinical_severity_pct=30.0,
        )
        self.assertEqual(safety.get("status"), "ok")
        self.assertEqual(safety.get("gate_label"), "Clear")
        self.assertGreaterEqual(float(safety.get("confidence_score", 0.0)), 70.0)
        self.assertGreater(float(safety.get("uncertainty", {}).get("boundary_distance_pct", 0.0)), 15.0)
        self.assertFalse(bool(safety.get("requires_clinician_review")))
        self.assertTrue(str(safety.get("clinical_justification", "")).strip())

    def test_biomarker_abnormality_triggers_safety_gate_even_when_risk_low(self):
        patient_data = {
            "age": 52,
            "sex": 1,
            "cp": 2,
            "trestbps": 126,
            "chol": 202,
            "fbs": 0,
            "restecg": 0,
            "thalach": 158,
            "exang": 0,
            "oldpeak": 0.6,
            "slope": 1,
            "ca": 0,
            "thal": 1,
            "bmi": 25.8,
            "smoking": 0,
            "diabetes": 0,
            "family_history": 0,
            "creatinine": 1.0,
            "bnp": 140,
            "troponin": 0.06,
            "ejection_fraction": 50,
        }
        probs = {"cad": 18.0, "hf": 16.0, "arr": 14.0, "mi": 12.0}
        safety = assess_prediction_safety(
            patient_data,
            probs,
            raw_master_pct=1.0,
            calibrated_master_pct=22.0,
            clinical_severity_pct=26.0,
        )
        self.assertIn(str(safety.get("status", "")), ("caution", "blocked"))
        self.assertTrue(bool(safety.get("requires_clinician_review")))
        trigger_flags = safety.get("uncertainty", {}).get("trigger_flags", {})
        self.assertTrue(bool(trigger_flags.get("biomarkers_abnormal")))
        self.assertTrue(any("Biomarker abnormality" in str(r) for r in safety.get("reasons", [])))

    def test_normal_biomarkers_keep_severity_near_low_30s(self):
        profile = {
            "age": 56,
            "sex": 1,
            "cp": 2,
            "trestbps": 138,
            "chol": 220,
            "fbs": 0,
            "restecg": 0,
            "thalach": 150,
            "exang": 0,
            "oldpeak": 0.7,
            "slope": 1,
            "ca": 1,
            "thal": 1,
            "bmi": 27.0,
            "smoking": 1,
            "diabetes": 1,
            "family_history": 1,
            "creatinine": 1.0,
            "bnp": 50,
            "troponin": 0.01,
            "ejection_fraction": 60,
        }
        severity = compute_clinical_severity_pct(profile)
        calibrated, clinical = calibrate_master_risk(3.0, profile)
        self.assertTrue(27.0 <= severity <= 33.0)
        self.assertAlmostEqual(severity, clinical, places=1)
        self.assertTrue(12.0 <= calibrated <= 15.0)

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

    def test_output_includes_safety_assessment_contract(self):
        out = generate_diagnosis(dict(DEFAULT_PATIENT))
        safety = out.get("safety_assessment", {})
        self.assertIsInstance(safety, dict)
        self.assertIn(str(safety.get("status", "")), ("ok", "caution", "blocked"))
        self.assertIn("gate_label", safety)
        self.assertIn("clinical_justification", safety)
        self.assertIn("summary", safety)
        self.assertIn("reasons", safety)
        self.assertEqual(bool(out.get("requires_clinician_review")), str(safety.get("status")) != "ok")
        self.assertEqual(bool(out.get("is_actionable_prediction")), str(safety.get("status")) == "ok")

    def test_extreme_profile_triggers_review_gate(self):
        extreme = {
            "age": 80,
            "sex": 1,
            "cp": 3,
            "trestbps": 200,
            "chol": 580,
            "fbs": 1,
            "restecg": 2,
            "thalach": 60,
            "exang": 1,
            "oldpeak": 7.0,
            "slope": 2,
            "ca": 3,
            "thal": 3,
            "bmi": 50.0,
            "smoking": 1,
            "diabetes": 1,
            "family_history": 1,
            "creatinine": 5.0,
            "bnp": 2000,
            "troponin": 4.0,
            "ejection_fraction": 15,
        }
        out = generate_diagnosis(extreme)
        safety = out.get("safety_assessment", {})
        self.assertIn(str(safety.get("status", "")), ("blocked", "caution"))
        self.assertTrue(out.get("requires_clinician_review"))
        self.assertFalse(out.get("is_actionable_prediction"))


if __name__ == "__main__":
    unittest.main()
