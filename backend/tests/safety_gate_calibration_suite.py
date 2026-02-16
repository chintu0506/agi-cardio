import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import generate_diagnosis, get_model_threshold_pct  # noqa: E402


TRIGGER_KEYS = ("risk_over_40", "biomarkers_abnormal", "confidence_below_40")

BASELINE_EXPECT = {
    "status_in": ["ok"],
    "confidence_min": 70.0,
    "boundary_min": 15.0,
    "risk_max": 25.0,
    "ood_max": 0,
    "triggers_all_false": list(TRIGGER_KEYS),
    "requires_clinician_review": False,
}

MILD_EXPECT = {
    "status_in": ["ok"],
    "confidence_min": 70.0,
    "boundary_min": 5.0,
    "risk_min": 25.0,
    "risk_max": 40.0,
    "ood_max": 0,
    "triggers_all_false": list(TRIGGER_KEYS),
    "requires_clinician_review": False,
}

ABNORMAL_EXPECT = {
    "status_in": ["caution", "blocked"],
    "triggers_any_true": list(TRIGGER_KEYS),
    "triggers_all_true": ["biomarkers_abnormal"],
    "requires_clinician_review": True,
}


def _case(case_id, category, payload, expect, description):
    return {
        "id": case_id,
        "category": category,
        "payload": payload,
        "expect": expect,
        "description": description,
    }


CALIBRATION_CASES = [
    _case(
        "baseline_01",
        "baseline",
        {
            "age": 42, "sex": 0, "cp": 2, "trestbps": 128, "chol": 168, "fbs": 0, "restecg": 0,
            "thalach": 179, "exang": 0, "oldpeak": 0.1, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 21.7, "smoking": 1, "diabetes": 1, "family_history": 0, "creatinine": 0.8,
            "bnp": 70, "troponin": 0.02, "ejection_fraction": 69,
        },
        dict(BASELINE_EXPECT),
        "Low-risk in-distribution baseline with normal biomarkers.",
    ),
    _case(
        "baseline_02",
        "baseline",
        {
            "age": 50, "sex": 0, "cp": 1, "trestbps": 128, "chol": 205, "fbs": 0, "restecg": 0,
            "thalach": 181, "exang": 0, "oldpeak": 0.5, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 21.8, "smoking": 0, "diabetes": 0, "family_history": 0, "creatinine": 0.8,
            "bnp": 42, "troponin": 0.02, "ejection_fraction": 64,
        },
        dict(BASELINE_EXPECT),
        "Healthy baseline with normal structural and biomarker profile.",
    ),
    _case(
        "baseline_03",
        "baseline",
        {
            "age": 58, "sex": 0, "cp": 1, "trestbps": 126, "chol": 201, "fbs": 0, "restecg": 0,
            "thalach": 168, "exang": 0, "oldpeak": 0.1, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 24.9, "smoking": 1, "diabetes": 1, "family_history": 0, "creatinine": 0.9,
            "bnp": 94, "troponin": 0.02, "ejection_fraction": 60,
        },
        dict(BASELINE_EXPECT),
        "Older baseline but still biomarker-normal and clear gate expected.",
    ),
    _case(
        "baseline_04",
        "baseline",
        {
            "age": 39, "sex": 0, "cp": 1, "trestbps": 110, "chol": 201, "fbs": 0, "restecg": 1,
            "thalach": 178, "exang": 0, "oldpeak": 0.4, "slope": 1, "ca": 1, "thal": 1,
            "bmi": 23.1, "smoking": 0, "diabetes": 0, "family_history": 1, "creatinine": 0.9,
            "bnp": 83, "troponin": 0.01, "ejection_fraction": 70,
        },
        dict(BASELINE_EXPECT),
        "Mild vessel history but preserved normal biomarker profile.",
    ),
    _case(
        "baseline_05",
        "baseline",
        {
            "age": 34, "sex": 0, "cp": 1, "trestbps": 115, "chol": 207, "fbs": 0, "restecg": 0,
            "thalach": 145, "exang": 0, "oldpeak": 0.4, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 23.1, "smoking": 0, "diabetes": 1, "family_history": 1, "creatinine": 0.9,
            "bnp": 71, "troponin": 0.01, "ejection_fraction": 58,
        },
        dict(BASELINE_EXPECT),
        "Younger baseline with family history and diabetes but normal stress markers.",
    ),
    _case(
        "baseline_06",
        "baseline",
        {
            "age": 54, "sex": 0, "cp": 2, "trestbps": 132, "chol": 208, "fbs": 0, "restecg": 1,
            "thalach": 170, "exang": 0, "oldpeak": 0.4, "slope": 0, "ca": 1, "thal": 1,
            "bmi": 25.0, "smoking": 0, "diabetes": 0, "family_history": 0, "creatinine": 1.2,
            "bnp": 63, "troponin": 0.01, "ejection_fraction": 61,
        },
        dict(BASELINE_EXPECT),
        "Borderline lifestyle factors but no biomarker trigger.",
    ),
    _case(
        "baseline_07",
        "baseline",
        {
            "age": 51, "sex": 0, "cp": 1, "trestbps": 108, "chol": 201, "fbs": 0, "restecg": 0,
            "thalach": 179, "exang": 0, "oldpeak": 0.1, "slope": 1, "ca": 0, "thal": 1,
            "bmi": 21.9, "smoking": 0, "diabetes": 1, "family_history": 0, "creatinine": 1.0,
            "bnp": 57, "troponin": 0.02, "ejection_fraction": 63,
        },
        dict(BASELINE_EXPECT),
        "Low-noise baseline with normal EF/Troponin/BNP.",
    ),
    _case(
        "baseline_08",
        "baseline",
        {
            "age": 35, "sex": 0, "cp": 2, "trestbps": 122, "chol": 195, "fbs": 0, "restecg": 1,
            "thalach": 164, "exang": 0, "oldpeak": 0.1, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 25.6, "smoking": 1, "diabetes": 0, "family_history": 1, "creatinine": 0.7,
            "bnp": 95, "troponin": 0.03, "ejection_fraction": 61,
        },
        dict(BASELINE_EXPECT),
        "Near-threshold BNP/troponin but still normal, should remain clear.",
    ),
    _case(
        "baseline_09",
        "baseline",
        {
            "age": 36, "sex": 0, "cp": 2, "trestbps": 128, "chol": 170, "fbs": 0, "restecg": 1,
            "thalach": 178, "exang": 0, "oldpeak": 0.3, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 25.7, "smoking": 0, "diabetes": 0, "family_history": 1, "creatinine": 1.1,
            "bnp": 83, "troponin": 0.03, "ejection_fraction": 68,
        },
        dict(BASELINE_EXPECT),
        "Low-risk profile with preserved function and normal biomarkers.",
    ),
    _case(
        "baseline_10",
        "baseline",
        {
            "age": 39, "sex": 1, "cp": 1, "trestbps": 114, "chol": 198, "fbs": 0, "restecg": 1,
            "thalach": 167, "exang": 0, "oldpeak": 0.7, "slope": 0, "ca": 0, "thal": 1,
            "bmi": 24.1, "smoking": 0, "diabetes": 0, "family_history": 0, "creatinine": 1.1,
            "bnp": 81, "troponin": 0.03, "ejection_fraction": 61,
        },
        dict(BASELINE_EXPECT),
        "Average baseline where gate should be clear and confident.",
    ),
    _case(
        "mild_01",
        "mild_risk",
        {
            "age": 58, "sex": 0, "cp": 3, "trestbps": 129, "chol": 197, "fbs": 0, "restecg": 0,
            "thalach": 142, "exang": 0, "oldpeak": 1.3, "slope": 2, "ca": 0, "thal": 1,
            "bmi": 29.0, "smoking": 1, "diabetes": 1, "family_history": 1, "creatinine": 0.9,
            "bnp": 57, "troponin": 0.02, "ejection_fraction": 67,
        },
        dict(MILD_EXPECT),
        "Mild-risk, normal biomarkers, should remain actionable.",
    ),
    _case(
        "mild_02",
        "mild_risk",
        {
            "age": 64, "sex": 1, "cp": 2, "trestbps": 122, "chol": 184, "fbs": 0, "restecg": 1,
            "thalach": 163, "exang": 0, "oldpeak": 0.4, "slope": 2, "ca": 1, "thal": 2,
            "bmi": 25.9, "smoking": 0, "diabetes": 0, "family_history": 1, "creatinine": 1.0,
            "bnp": 36, "troponin": 0.02, "ejection_fraction": 60,
        },
        dict(MILD_EXPECT),
        "Mild-risk profile with vessel history but no abnormal biomarker.",
    ),
    _case(
        "mild_03",
        "mild_risk",
        {
            "age": 50, "sex": 0, "cp": 3, "trestbps": 123, "chol": 191, "fbs": 0, "restecg": 0,
            "thalach": 147, "exang": 0, "oldpeak": 1.6, "slope": 2, "ca": 0, "thal": 2,
            "bmi": 24.6, "smoking": 1, "diabetes": 0, "family_history": 1, "creatinine": 0.9,
            "bnp": 89, "troponin": 0.02, "ejection_fraction": 67,
        },
        dict(MILD_EXPECT),
        "Mild-risk with asymptomatic chest-pain class and normal stress markers.",
    ),
    _case(
        "mild_04",
        "mild_risk",
        {
            "age": 54, "sex": 0, "cp": 2, "trestbps": 143, "chol": 240, "fbs": 0, "restecg": 1,
            "thalach": 149, "exang": 0, "oldpeak": 1.4, "slope": 2, "ca": 1, "thal": 1,
            "bmi": 28.4, "smoking": 1, "diabetes": 0, "family_history": 1, "creatinine": 1.0,
            "bnp": 76, "troponin": 0.01, "ejection_fraction": 65,
        },
        dict(MILD_EXPECT),
        "Mild-risk with higher cholesterol and BP but no biomarker trigger.",
    ),
    _case(
        "mild_05",
        "mild_risk",
        {
            "age": 55, "sex": 1, "cp": 3, "trestbps": 141, "chol": 187, "fbs": 0, "restecg": 1,
            "thalach": 150, "exang": 0, "oldpeak": 1.3, "slope": 1, "ca": 0, "thal": 1,
            "bmi": 24.9, "smoking": 0, "diabetes": 0, "family_history": 0, "creatinine": 0.9,
            "bnp": 62, "troponin": 0.02, "ejection_fraction": 67,
        },
        dict(MILD_EXPECT),
        "Moderate symptom burden but normal objective biomarker profile.",
    ),
    _case(
        "mild_06",
        "mild_risk",
        {
            "age": 61, "sex": 0, "cp": 2, "trestbps": 143, "chol": 206, "fbs": 0, "restecg": 0,
            "thalach": 160, "exang": 0, "oldpeak": 0.9, "slope": 0, "ca": 1, "thal": 2,
            "bmi": 25.4, "smoking": 1, "diabetes": 0, "family_history": 0, "creatinine": 0.9,
            "bnp": 51, "troponin": 0.01, "ejection_fraction": 58,
        },
        dict(MILD_EXPECT),
        "Upper-mild risk band with still-normal biomarkers.",
    ),
    _case(
        "abnormal_01",
        "true_abnormal",
        {
            "age": 52, "sex": 1, "cp": 2, "trestbps": 126, "chol": 202, "fbs": 0, "restecg": 0,
            "thalach": 158, "exang": 0, "oldpeak": 0.6, "slope": 1, "ca": 0, "thal": 1,
            "bmi": 25.8, "smoking": 0, "diabetes": 0, "family_history": 0, "creatinine": 1.0,
            "bnp": 140, "troponin": 0.06, "ejection_fraction": 50,
        },
        dict(ABNORMAL_EXPECT),
        "Low calibrated risk but biomarker abnormality should trigger gate.",
    ),
    _case(
        "abnormal_02",
        "true_abnormal",
        {
            "age": 52, "sex": 1, "cp": 2, "trestbps": 126, "chol": 202, "fbs": 0, "restecg": 0,
            "thalach": 158, "exang": 0, "oldpeak": 0.6, "slope": 1, "ca": 0, "thal": 1,
            "bmi": 25.8, "smoking": 0, "diabetes": 0, "family_history": 0, "creatinine": 1.0,
            "bnp": 80, "troponin": 0.08, "ejection_fraction": 60,
        },
        dict(ABNORMAL_EXPECT),
        "Isolated troponin elevation should activate provisional gate.",
    ),
    _case(
        "abnormal_03",
        "true_abnormal",
        {
            "age": 55, "sex": 0, "cp": 2, "trestbps": 130, "chol": 210, "fbs": 0, "restecg": 1,
            "thalach": 145, "exang": 0, "oldpeak": 0.9, "slope": 1, "ca": 1, "thal": 1,
            "bmi": 27.2, "smoking": 0, "diabetes": 1, "family_history": 1, "creatinine": 1.0,
            "bnp": 420, "troponin": 0.02, "ejection_fraction": 57,
        },
        dict(ABNORMAL_EXPECT),
        "BNP elevation should force safety review.",
    ),
    _case(
        "abnormal_04",
        "true_abnormal",
        {
            "age": 60, "sex": 1, "cp": 2, "trestbps": 138, "chol": 230, "fbs": 0, "restecg": 1,
            "thalach": 140, "exang": 0, "oldpeak": 1.2, "slope": 1, "ca": 1, "thal": 2,
            "bmi": 28.0, "smoking": 1, "diabetes": 1, "family_history": 1, "creatinine": 1.1,
            "bnp": 90, "troponin": 0.02, "ejection_fraction": 49,
        },
        dict(ABNORMAL_EXPECT),
        "Reduced EF should trigger clinician review.",
    ),
    _case(
        "abnormal_05",
        "true_abnormal",
        {
            "age": 63, "sex": 1, "cp": 3, "trestbps": 150, "chol": 260, "fbs": 1, "restecg": 1,
            "thalach": 125, "exang": 1, "oldpeak": 2.5, "slope": 2, "ca": 2, "thal": 2,
            "bmi": 30.2, "smoking": 1, "diabetes": 1, "family_history": 1, "creatinine": 1.4,
            "bnp": 550, "troponin": 0.2, "ejection_fraction": 42,
        },
        dict(ABNORMAL_EXPECT),
        "Multi-signal abnormal profile should be caution/blocked.",
    ),
    _case(
        "abnormal_06",
        "true_abnormal",
        {
            "age": 72, "sex": 0, "cp": 2, "trestbps": 155, "chol": 218, "fbs": 1, "restecg": 1,
            "thalach": 108, "exang": 0, "oldpeak": 1.5, "slope": 1, "ca": 1, "thal": 1,
            "bmi": 33.1, "smoking": 0, "diabetes": 1, "family_history": 1, "creatinine": 1.8,
            "bnp": 850, "troponin": 0.08, "ejection_fraction": 38,
        },
        dict(ABNORMAL_EXPECT),
        "High-risk preset with abnormal biomarkers and low EF.",
    ),
    _case(
        "abnormal_07",
        "true_abnormal",
        {
            "age": 68, "sex": 1, "cp": 3, "trestbps": 168, "chol": 295, "fbs": 1, "restecg": 1,
            "thalach": 98, "exang": 1, "oldpeak": 4.2, "slope": 2, "ca": 3, "thal": 3,
            "bmi": 31.2, "smoking": 1, "diabetes": 1, "family_history": 1, "creatinine": 1.4,
            "bnp": 620, "troponin": 1.2, "ejection_fraction": 32,
        },
        dict(ABNORMAL_EXPECT),
        "Critical ischemic/injury profile should strongly block.",
    ),
    _case(
        "abnormal_08",
        "true_abnormal",
        {
            "age": 80, "sex": 1, "cp": 3, "trestbps": 200, "chol": 580, "fbs": 1, "restecg": 2,
            "thalach": 60, "exang": 1, "oldpeak": 7.0, "slope": 2, "ca": 3, "thal": 3,
            "bmi": 50.0, "smoking": 1, "diabetes": 1, "family_history": 1, "creatinine": 5.0,
            "bnp": 2000, "troponin": 4.0, "ejection_fraction": 15,
        },
        dict(ABNORMAL_EXPECT),
        "Extreme outlier profile should be blocked with low confidence.",
    ),
]


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return int(default)


def _check(name, passed, actual=None, expected=None):
    return {
        "name": str(name),
        "passed": bool(passed),
        "actual": actual,
        "expected": expected,
    }


def evaluate_case(case):
    payload = dict(case.get("payload") or {})
    expect = dict(case.get("expect") or {})
    out = generate_diagnosis(payload)
    safety = out.get("safety_assessment") or {}
    uncertainty = safety.get("uncertainty") or {}
    trigger_flags = uncertainty.get("trigger_flags") or {}
    normalized_triggers = {k: bool(trigger_flags.get(k)) for k in TRIGGER_KEYS}

    metrics = {
        "risk": _safe_float(out.get("master_probability"), 0.0),
        "raw_model_probability": _safe_float(out.get("raw_model_probability"), 0.0),
        "clinical_severity_score": _safe_float(out.get("clinical_severity_score"), 0.0),
        "status": str(safety.get("status", "")),
        "gate_label": str(safety.get("gate_label", "")),
        "confidence_score": _safe_float(safety.get("confidence_score"), 0.0),
        "boundary_distance_pct": _safe_float(uncertainty.get("boundary_distance_pct"), 0.0),
        "ood_feature_count": _safe_int(uncertainty.get("ood_feature_count"), 0),
        "requires_clinician_review": bool(out.get("requires_clinician_review", False)),
        "trigger_flags": normalized_triggers,
    }

    checks = []
    if "status_in" in expect:
        allowed = [str(s) for s in expect["status_in"]]
        checks.append(_check("status_in", metrics["status"] in allowed, metrics["status"], allowed))
    if "confidence_min" in expect:
        checks.append(
            _check(
                "confidence_min",
                metrics["confidence_score"] >= float(expect["confidence_min"]),
                metrics["confidence_score"],
                float(expect["confidence_min"]),
            )
        )
    if "boundary_min" in expect:
        checks.append(
            _check(
                "boundary_min",
                metrics["boundary_distance_pct"] >= float(expect["boundary_min"]),
                metrics["boundary_distance_pct"],
                float(expect["boundary_min"]),
            )
        )
    if "risk_min" in expect:
        checks.append(
            _check(
                "risk_min",
                metrics["risk"] >= float(expect["risk_min"]),
                metrics["risk"],
                float(expect["risk_min"]),
            )
        )
    if "risk_max" in expect:
        checks.append(
            _check(
                "risk_max",
                metrics["risk"] < float(expect["risk_max"]),
                metrics["risk"],
                float(expect["risk_max"]),
            )
        )
    if "ood_max" in expect:
        checks.append(
            _check(
                "ood_max",
                metrics["ood_feature_count"] <= int(expect["ood_max"]),
                metrics["ood_feature_count"],
                int(expect["ood_max"]),
            )
        )
    if "requires_clinician_review" in expect:
        expected_flag = bool(expect["requires_clinician_review"])
        checks.append(
            _check(
                "requires_clinician_review",
                metrics["requires_clinician_review"] == expected_flag,
                metrics["requires_clinician_review"],
                expected_flag,
            )
        )
    for key in expect.get("triggers_all_false", []):
        checks.append(
            _check(
                f"trigger_{key}_false",
                not bool(normalized_triggers.get(key)),
                bool(normalized_triggers.get(key)),
                False,
            )
        )
    for key in expect.get("triggers_all_true", []):
        checks.append(
            _check(
                f"trigger_{key}_true",
                bool(normalized_triggers.get(key)),
                bool(normalized_triggers.get(key)),
                True,
            )
        )
    trigger_any = list(expect.get("triggers_any_true") or [])
    if trigger_any:
        any_true = any(bool(normalized_triggers.get(k)) for k in trigger_any)
        checks.append(
            _check(
                "triggers_any_true",
                any_true,
                {k: bool(normalized_triggers.get(k)) for k in trigger_any},
                True,
            )
        )

    failed_checks = [c["name"] for c in checks if not c["passed"]]
    return {
        "id": str(case.get("id", "")),
        "category": str(case.get("category", "")),
        "description": str(case.get("description", "")),
        "all_checks_passed": len(failed_checks) == 0,
        "failed_checks": failed_checks,
        "checks": checks,
        "metrics": metrics,
    }


def run_calibration_suite(cases=None):
    case_pack = list(cases or CALIBRATION_CASES)
    results = [evaluate_case(case) for case in case_pack]
    total = len(results)
    passed = sum(1 for r in results if r["all_checks_passed"])
    failed = total - passed
    by_category = {}
    for row in results:
        cat = row["category"]
        bucket = by_category.setdefault(cat, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        if row["all_checks_passed"]:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1
    for bucket in by_category.values():
        total_cat = max(1, int(bucket["total"]))
        bucket["pass_rate_pct"] = round((float(bucket["passed"]) * 100.0) / total_cat, 1)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "master_threshold_pct": float(get_model_threshold_pct("master")),
        "summary": {
            "total_cases": total,
            "passed_cases": passed,
            "failed_cases": failed,
            "pass_rate_pct": round((float(passed) * 100.0 / max(1, total)), 1),
        },
        "categories": by_category,
        "cases": results,
    }
