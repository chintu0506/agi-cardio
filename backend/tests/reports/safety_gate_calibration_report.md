# Safety Gate Calibration Report

- Generated At (UTC): `2026-02-16T05:23:10.298168+00:00`
- Master Threshold: `17.0%`
- Total Cases: `24`
- Passed Cases: `24`
- Failed Cases: `0`
- Pass Rate: `100.0%`

## Acceptance Targets

- Baseline cases: `status=ok`, `confidence>=70`, `boundary>15%`, `OOD=0`.
- Mild-risk cases: `25%<=risk<40%`, `status=ok`, `confidence>=70`, `OOD=0`.
- True-abnormal cases: `status in {caution, blocked}` with biomarker trigger.

## Category Summary

| Category | Cases | Passed | Failed | Pass Rate |
|---|---:|---:|---:|---:|
| baseline | 10 | 10 | 0 | 100.0% |
| mild_risk | 6 | 6 | 0 | 100.0% |
| true_abnormal | 8 | 8 | 0 | 100.0% |

## Case Results

| Case | Category | Risk | Status | Confidence | Boundary | OOD | Triggers | Pass | Failed Checks |
|---|---|---:|---|---:|---:|---:|---|---|---|
| baseline_01 | baseline | 4.6% | ok | 89.7 | 17.0% | 0 | none | PASS | - |
| baseline_02 | baseline | 4.6% | ok | 91.2 | 17.0% | 0 | none | PASS | - |
| baseline_03 | baseline | 8.7% | ok | 91.6 | 17.0% | 0 | none | PASS | - |
| baseline_04 | baseline | 8.0% | ok | 90.8 | 15.1% | 0 | none | PASS | - |
| baseline_05 | baseline | 4.9% | ok | 91.1 | 17.0% | 0 | none | PASS | - |
| baseline_06 | baseline | 8.8% | ok | 92.1 | 15.1% | 0 | none | PASS | - |
| baseline_07 | baseline | 6.1% | ok | 90.8 | 17.0% | 0 | none | PASS | - |
| baseline_08 | baseline | 3.0% | ok | 93.2 | 17.0% | 0 | none | PASS | - |
| baseline_09 | baseline | 1.5% | ok | 92.1 | 17.0% | 0 | none | PASS | - |
| baseline_10 | baseline | 2.7% | ok | 93.3 | 17.0% | 0 | none | PASS | - |
| mild_01 | mild_risk | 25.2% | ok | 88.9 | 8.3% | 0 | none | PASS | - |
| mild_02 | mild_risk | 25.7% | ok | 85.2 | 11.0% | 0 | none | PASS | - |
| mild_03 | mild_risk | 26.6% | ok | 84.3 | 13.0% | 0 | none | PASS | - |
| mild_04 | mild_risk | 27.2% | ok | 84.1 | 7.2% | 0 | none | PASS | - |
| mild_05 | mild_risk | 28.3% | ok | 83.5 | 15.8% | 0 | none | PASS | - |
| mild_06 | mild_risk | 35.0% | ok | 85.5 | 19.9% | 0 | none | PASS | - |
| abnormal_01 | true_abnormal | 13.3% | caution | 76.0 | 15.1% | 0 | biomarkers_abnormal | PASS | - |
| abnormal_02 | true_abnormal | 9.9% | caution | 78.7 | 15.1% | 0 | biomarkers_abnormal | PASS | - |
| abnormal_03 | true_abnormal | 30.4% | blocked | 63.5 | 3.8% | 0 | biomarkers_abnormal | PASS | - |
| abnormal_04 | true_abnormal | 60.0% | caution | 79.1 | 46.7% | 0 | risk_over_40,biomarkers_abnormal | PASS | - |
| abnormal_05 | true_abnormal | 99.0% | blocked | 64.0 | 82.0% | 0 | risk_over_40,biomarkers_abnormal | PASS | - |
| abnormal_06 | true_abnormal | 66.7% | blocked | 45.7 | 39.1% | 1 | risk_over_40,biomarkers_abnormal | PASS | - |
| abnormal_07 | true_abnormal | 96.6% | blocked | 22.8 | 78.1% | 1 | risk_over_40,biomarkers_abnormal,confidence_below_40 | PASS | - |
| abnormal_08 | true_abnormal | 92.4% | blocked | 20.8 | 71.4% | 7 | risk_over_40,biomarkers_abnormal,confidence_below_40 | PASS | - |
