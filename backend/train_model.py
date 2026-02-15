"""
AGI Cardiovascular Diagnostic System — Advanced Multi-Model Trainer
Trains separate classifiers for 4 cardiovascular conditions plus
a master risk ensemble, mimicking a multimodal AGI reasoning framework.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import (RandomForestClassifier, GradientBoostingClassifier,
                               VotingClassifier, ExtraTreesClassifier, StackingClassifier)
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import (accuracy_score, roc_auc_score, classification_report,
                              confusion_matrix, brier_score_loss, log_loss,
                              average_precision_score)
from sklearn.calibration import calibration_curve
from sklearn.base import clone
import joblib
import json
import os
from datetime import datetime, timezone
try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None
try:
    import shap
except Exception:
    shap = None

np.random.seed(2024)

FEATURE_COLS = [
    'age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 'restecg',
    'thalach', 'exang', 'oldpeak', 'slope', 'ca', 'thal',
    # Extended features for AGI system
    'bmi', 'smoking', 'diabetes', 'family_history',
    'creatinine', 'bnp', 'troponin', 'ejection_fraction'
]

MASTER_DATASET_CANDIDATES = [
    'data/heart.csv',
    'heart.csv',
    'data/cleveland_heart.csv',
    'data/heart_disease.csv',
]

UCI_DIR_CANDIDATES = [
    '/Users/chintuboppana/Downloads/heart+disease',
    'data/heart+disease',
]

HF_DATASET_CANDIDATES = [
    '/Users/chintuboppana/Downloads/heart_failure_clinical_records_dataset.csv',
    'data/heart_failure_clinical_records_dataset.csv',
]

SAHEART_CANDIDATES = [
    '/Users/chintuboppana/Downloads/SAHeart.csv',
    '/Users/chintuboppana/Downloads/SAheart.csv',
    '/Users/chintuboppana/Downloads/SAheart.RData',
    'data/SAheart.csv',
    'data/SAheart.RData',
]

MASTER_SYNTH_FACTOR = 5.0
SPLIT_INDEX_PATH = 'models/train_test_splits.json'


def _first_existing(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None


def _to_binary01(x):
    return (pd.to_numeric(x, errors='coerce').fillna(0) > 0).astype(int)


def load_hf_support_dataset():
    hf_path = _first_existing(HF_DATASET_CANDIDATES)
    if not hf_path:
        return None, None
    try:
        hf = pd.read_csv(hf_path)
        cols = {c.lower(): c for c in hf.columns}
        out = pd.DataFrame()
        out['sex'] = _to_binary01(hf[cols.get('sex', list(hf.columns)[0])])
        out['smoking'] = _to_binary01(hf[cols.get('smoking', list(hf.columns)[0])])
        out['diabetes'] = _to_binary01(hf[cols.get('diabetes', list(hf.columns)[0])])
        out['creatinine'] = pd.to_numeric(hf[cols.get('serum_creatinine', list(hf.columns)[0])], errors='coerce')
        out['ejection_fraction'] = pd.to_numeric(hf[cols.get('ejection_fraction', list(hf.columns)[0])], errors='coerce')
        out = out.replace([np.inf, -np.inf], np.nan).dropna()
        if len(out) < 50:
            return None, None
        return out.reset_index(drop=True), hf_path
    except Exception:
        return None, None


def load_saheart_family_history_rate():
    sa_path = _first_existing(SAHEART_CANDIDATES)
    if not sa_path:
        return None, None
    try:
        if sa_path.lower().endswith('.csv'):
            sa = pd.read_csv(sa_path)
        else:
            # Optional support: if pyreadr exists in env, use it; otherwise caller falls back.
            import pyreadr  # type: ignore
            r = pyreadr.read_r(sa_path)
            sa = list(r.values())[0]
        fam_col = None
        for c in sa.columns:
            if str(c).lower() in ('famhist', 'family_history'):
                fam_col = c
                break
        if fam_col is None:
            return None, sa_path
        s = sa[fam_col].astype(str).str.lower()
        rate = float(s.isin(['1', 'yes', 'true', 'present']).mean())
        if rate <= 0.0:
            rate = float(pd.to_numeric(sa[fam_col], errors='coerce').fillna(0).gt(0).mean())
        return min(max(rate, 0.05), 0.95), sa_path
    except Exception:
        return None, sa_path


def _build_extended_features(base, hf_support, fam_rate):
    n = len(base)
    ext = pd.DataFrame(index=base.index)

    # BMI proxy from pressure/cholesterol with realistic spread.
    ext['bmi'] = np.clip(
        23.0 + 0.03 * (base['trestbps'] - 120) + 0.012 * (base['chol'] - 200) + np.random.normal(0, 2.8, n),
        16, 48
    ).round(1)

    smoke_base = 0.33
    dm_base = 0.22
    if hf_support is not None and len(hf_support) > 20:
        smoke_base = float(hf_support['smoking'].mean())
        dm_base = float(hf_support['diabetes'].mean())
        creat_pool = hf_support['creatinine'].to_numpy()
        ef_pool = hf_support['ejection_fraction'].to_numpy()
    else:
        creat_pool = np.clip(np.random.normal(1.0, 0.25, 600), 0.4, 4.5)
        ef_pool = np.clip(np.random.normal(55, 9, 600), 20, 80)

    # Sex/age/risk-adjusted lifestyle covariates.
    smoke_p = np.clip(smoke_base + 0.06 * (base['sex'] == 1) + 0.03 * (base['age'] < 50), 0.05, 0.85)
    ext['smoking'] = (np.random.rand(n) < smoke_p).astype(int)

    dm_p = np.clip(dm_base + 0.12 * (base['fbs'] > 0) + 0.04 * (base['chol'] > 240), 0.05, 0.9)
    ext['diabetes'] = (np.random.rand(n) < dm_p).astype(int)

    fam_p = fam_rate if fam_rate is not None else 0.42
    ext['family_history'] = (np.random.rand(n) < fam_p).astype(int)

    ext['creatinine'] = np.clip(np.random.choice(creat_pool, size=n, replace=True) + np.random.normal(0, 0.08, n), 0.4, 4.5)
    ef_base = np.random.choice(ef_pool, size=n, replace=True)
    ef_adjust = -5.0 * (base['exang'] > 0) - 7.0 * (base['ca'] > 1) - 4.0 * (base['oldpeak'] > 2.0) + 2.0 * (base['thalach'] > 145)
    ext['ejection_fraction'] = np.clip(ef_base + ef_adjust + np.random.normal(0, 2.0, n), 20, 80)

    # Lab priors with dependence on ischemic/functional burden.
    bnp_raw = (
        np.random.exponential(110, n)
        + 120 * (ext['ejection_fraction'] < 45).astype(float)
        + 60 * (base['age'] > 65).astype(float)
        + 40 * (ext['creatinine'] > 1.5).astype(float)
        + 25 * (base['ca'] > 1).astype(float)
    )
    ext['bnp'] = np.clip(bnp_raw, 5, 2000).round(1)

    trop_raw = (
        np.random.exponential(0.03, n)
        + 0.09 * (base['cp'] >= 2).astype(float)
        + 0.07 * (base['oldpeak'] > 2.0).astype(float)
        + 0.06 * (base['ca'] > 1).astype(float)
        + 0.03 * (base['exang'] > 0).astype(float)
    )
    ext['troponin'] = np.clip(trop_raw, 0.001, 3.5).round(3)
    return ext


def load_real_master_dataset():
    """
    Load real-world training rows from UCI processed heart files and enrich to 21-feature schema
    using HF and SAheart side datasets where available.
    """
    uci_dir = _first_existing(UCI_DIR_CANDIDATES)
    if not uci_dir:
        return None, None, None

    processed_files = [
        'processed.cleveland.data',
        'processed.hungarian.data',
        'processed.switzerland.data',
        'processed.va.data',
    ]
    rows = []
    for fn in processed_files:
        p = os.path.join(uci_dir, fn)
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p, header=None)
        if df.shape[1] != 14:
            continue
        rows.append(df)

    if not rows:
        return None, None, None

    raw = pd.concat(rows, axis=0, ignore_index=True)
    raw.columns = ['age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 'restecg', 'thalach', 'exang', 'oldpeak', 'slope', 'ca', 'thal', 'target']
    raw = raw.replace('?', np.nan)
    for c in raw.columns:
        raw[c] = pd.to_numeric(raw[c], errors='coerce')

    # UCI coding normalization -> project coding.
    raw['cp'] = raw['cp'] - 1           # 1..4 -> 0..3
    raw['slope'] = raw['slope'] - 1     # 1..3 -> 0..2
    raw['thal'] = raw['thal'].replace({3: 1, 6: 2, 7: 3})

    # Core imputation for sparse UCI fields.
    for c in ['ca', 'thal', 'slope', 'oldpeak', 'chol', 'trestbps', 'thalach']:
        raw[c] = raw[c].fillna(raw[c].median())
    for c in ['sex', 'fbs', 'restecg', 'exang', 'cp']:
        raw[c] = raw[c].fillna(raw[c].mode().iloc[0] if not raw[c].mode().empty else 0)

    base = raw[['age', 'sex', 'cp', 'trestbps', 'chol', 'fbs', 'restecg', 'thalach', 'exang', 'oldpeak', 'slope', 'ca', 'thal']].copy()
    base['cp'] = base['cp'].clip(0, 3)
    base['slope'] = base['slope'].clip(0, 2)
    base['ca'] = base['ca'].clip(0, 3)
    base['thal'] = base['thal'].clip(1, 3)

    hf_support, hf_path = load_hf_support_dataset()
    fam_rate, sa_path = load_saheart_family_history_rate()
    ext = _build_extended_features(base, hf_support, fam_rate)
    full = pd.concat([base.reset_index(drop=True), ext.reset_index(drop=True)], axis=1)[FEATURE_COLS]
    y = _to_binary01(raw['target']).reset_index(drop=True)

    full = full.replace([np.inf, -np.inf], np.nan)
    valid_idx = full.dropna().index
    full = full.loc[valid_idx].reset_index(drop=True)
    y = y.loc[valid_idx].reset_index(drop=True)
    if len(full) < 200:
        return None, None, None

    source = {
        'uci_dir': uci_dir,
        'uci_rows': int(len(full)),
        'hf_support_path': hf_path,
        'hf_support_rows': int(len(hf_support)) if hf_support is not None else 0,
        'saheart_path': sa_path,
        'family_history_rate': round(float(fam_rate), 3) if fam_rate is not None else None,
    }
    return full, y, source

def generate_dataset(n=2500):
    """Generate rich multimodal cardiovascular dataset."""
    d = {}
    d['age']             = np.clip(np.random.normal(55, 11, n), 20, 85).astype(int)
    d['sex']             = np.random.choice([0,1], n, p=[0.38, 0.62])
    d['cp']              = np.random.choice([0,1,2,3], n, p=[0.09,0.16,0.27,0.48])
    d['trestbps']        = np.clip(np.random.normal(132, 18, n), 90, 210).astype(int)
    d['chol']            = np.clip(np.random.normal(248, 53, n), 120, 580).astype(int)
    d['fbs']             = np.random.choice([0,1], n, p=[0.84, 0.16])
    d['restecg']         = np.random.choice([0,1,2], n, p=[0.47,0.51,0.02])
    base_hr              = 210 - 0.8 * np.array(d['age'])
    d['thalach']         = np.clip(base_hr + np.random.normal(0,22,n), 65, 205).astype(int)
    d['exang']           = np.random.choice([0,1], n, p=[0.67, 0.33])
    d['oldpeak']         = np.clip(np.round(np.random.exponential(1.05, n), 1), 0, 6.5)
    d['slope']           = np.random.choice([0,1,2], n, p=[0.20,0.47,0.33])
    d['ca']              = np.random.choice([0,1,2,3], n, p=[0.57,0.22,0.13,0.08])
    d['thal']            = np.random.choice([1,2,3], n, p=[0.54,0.08,0.38])
    # Extended biomarkers
    d['bmi']             = np.clip(np.random.normal(27.5, 5.0, n), 16, 48).round(1)
    d['smoking']         = np.random.choice([0,1], n, p=[0.65, 0.35])
    d['diabetes']        = np.random.choice([0,1], n, p=[0.78, 0.22])
    d['family_history']  = np.random.choice([0,1], n, p=[0.60, 0.40])
    d['creatinine']      = np.clip(np.random.normal(1.05, 0.4, n), 0.4, 4.5).round(2)
    d['bnp']             = np.clip(np.random.exponential(120, n), 5, 2000).astype(int)
    d['troponin']        = np.clip(np.random.exponential(0.06, n), 0.001, 3.5).round(3)
    d['ejection_fraction']= np.clip(np.random.normal(58, 12, n), 20, 80).astype(int)

    df = pd.DataFrame(d)

    # --- Coronary Artery Disease ---
    cad = (
        (df.cp == 3)*2.5 + (df.exang==1)*2.0 + (df.oldpeak>2)*1.8 +
        (df.ca>0)*1.8 + (df.thal==3)*2.0 + (df.trestbps>145)*0.9 +
        (df.chol>260)*0.7 + (df.smoking==1)*0.8 + (df.diabetes==1)*0.9 +
        (df.age>60)*1.2 + np.random.normal(0, 0.6, n)
    )
    df['cad'] = (cad > np.percentile(cad, 52)).astype(int)

    # --- Heart Failure ---
    hf = (
        (df.thalach<115)*2.2 + (df.ejection_fraction<45)*3.5 +
        (df.bnp>400)*2.5 + (df.restecg==1)*1.5 + (df.trestbps>165)*1.4 +
        (df.bmi>32)*0.9 + (df.diabetes==1)*0.8 + (df.creatinine>2)*1.2 +
        (df.age>65)*1.3 + np.random.normal(0, 0.6, n)
    )
    df['hf'] = (hf > np.percentile(hf, 68)).astype(int)

    # --- Arrhythmia ---
    arr = (
        (df.restecg==1)*2.5 + (df.thalach>175)*1.5 + (df.fbs==1)*1.0 +
        (df.oldpeak>1.5)*1.2 + (df.slope==2)*1.0 + (df.age>55)*0.8 +
        (df.smoking==1)*0.6 + np.random.normal(0, 0.7, n)
    )
    df['arr'] = (arr > np.percentile(arr, 70)).astype(int)

    # --- Myocardial Infarction ---
    mi = (
        (df.troponin>0.4)*3.5 + (df.cp==3)*2.2 + (df.oldpeak>3)*2.0 +
        (df.ca>1)*1.8 + (df.exang==1)*1.5 + (df.thal==3)*1.8 +
        (df.slope==2)*1.2 + (df.sex==1)*0.8 + (df.age>58)*1.1 +
        np.random.normal(0, 0.5, n)
    )
    df['mi'] = (mi > np.percentile(mi, 78)).astype(int)

    # Master risk
    risk = (
        (df.cp==3)*2.2 + (df.thal==3)*2.0 + (df.oldpeak)*0.55 +
        (df.ca>0)*1.8 + (df.exang==1)*1.6 + (df.age>60)*1.4 +
        (df.thalach<120)*1.4 + (df.ejection_fraction<45)*2.0 +
        (df.troponin>0.2)*2.0 + (df.bnp>300)*1.5 +
        (df.sex==1)*0.5 + (df.diabetes==1)*0.8 + (df.smoking==1)*0.7 +
        np.random.normal(0, 0.6, n)
    )
    df['target'] = (risk > np.percentile(risk, 48)).astype(int)
    return df

def build_candidates():
    """Diverse candidates; pick best per target by CV AUC."""
    rf_a = RandomForestClassifier(
        n_estimators=450, max_depth=12, min_samples_leaf=2,
        class_weight='balanced_subsample', random_state=42, n_jobs=-1
    )
    et_a = ExtraTreesClassifier(
        n_estimators=400, max_depth=12, min_samples_leaf=2,
        class_weight='balanced', random_state=42, n_jobs=-1
    )
    gb_a = GradientBoostingClassifier(n_estimators=260, max_depth=3, learning_rate=0.05, random_state=42)
    lr_a = LogisticRegression(C=1.2, max_iter=2000, random_state=42)
    vote_a = VotingClassifier(
        [('rf', rf_a), ('et', et_a), ('gb', gb_a), ('lr', lr_a)],
        voting='soft',
        weights=[3, 3, 2, 1],
    )

    rf_b = RandomForestClassifier(
        n_estimators=700, max_depth=16, min_samples_leaf=1,
        class_weight='balanced_subsample', random_state=42, n_jobs=-1
    )
    et_b = ExtraTreesClassifier(
        n_estimators=600, max_depth=16, min_samples_leaf=1,
        class_weight='balanced', random_state=42, n_jobs=-1
    )
    gb_b = GradientBoostingClassifier(n_estimators=320, max_depth=4, learning_rate=0.04, random_state=42)
    lr_b = LogisticRegression(C=1.8, max_iter=2500, random_state=42)
    vote_b = VotingClassifier(
        [('rf', rf_b), ('et', et_b), ('gb', gb_b), ('lr', lr_b)],
        voting='soft',
        weights=[4, 3, 2, 1],
    )

    stack = StackingClassifier(
        estimators=[
            ('rf', RandomForestClassifier(
                n_estimators=500, max_depth=14, min_samples_leaf=2,
                class_weight='balanced_subsample', random_state=42, n_jobs=-1
            )),
            ('et', ExtraTreesClassifier(
                n_estimators=500, max_depth=14, min_samples_leaf=2,
                class_weight='balanced', random_state=42, n_jobs=-1
            )),
            ('gb', GradientBoostingClassifier(n_estimators=260, max_depth=3, learning_rate=0.05, random_state=42)),
        ],
        final_estimator=LogisticRegression(C=1.2, max_iter=2500, random_state=42),
        passthrough=True,
        n_jobs=1,
        cv=3,
    )
    if XGBClassifier is not None:
        xgb = XGBClassifier(
            n_estimators=350, max_depth=4, learning_rate=0.05,
            subsample=0.9, colsample_bytree=0.9,
            eval_metric='logloss', random_state=42, n_jobs=1
        )
        return [('xgboost', xgb), ('voting_a', vote_a), ('voting_b', vote_b), ('stacking', stack)]
    return [('voting_a', vote_a), ('voting_b', vote_b), ('stacking', stack)]

def train_tuned_xgboost(X_tr, y_tr):
    if XGBClassifier is None:
        return None, None
    base = XGBClassifier(
        objective='binary:logistic',
        eval_metric='logloss',
        random_state=42,
        n_jobs=1,
    )
    param_grid = {
        'n_estimators': [120, 220],
        'max_depth': [3, 5, 7],
        'learning_rate': [0.01, 0.1],
        'subsample': [0.8, 1.0],
    }
    cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    grid = GridSearchCV(
        estimator=base,
        param_grid=param_grid,
        cv=cv,
        scoring='roc_auc',
        n_jobs=1,
        refit=True,
    )
    grid.fit(X_tr, y_tr)
    return grid.best_estimator_, float(grid.best_score_)


def select_threshold(y_true, y_prob):
    thresholds = np.linspace(0.2, 0.8, 61)
    best_t = 0.5
    best_acc = -1.0
    for t in thresholds:
        pred = (y_prob >= t).astype(int)
        acc = accuracy_score(y_true, pred)
        if acc > best_acc:
            best_acc = acc
            best_t = float(t)
    return best_t, float(best_acc)


def risk_tier_label(prob_pct):
    if prob_pct <= 40:
        return 'LOW'
    if prob_pct <= 70:
        return 'MODERATE'
    if prob_pct < 85:
        return 'HIGH'
    return 'CRITICAL'


def build_eval_metrics(y_true, y_prob, y_pred):
    y_true_arr = np.asarray(y_true).astype(int)
    y_prob_arr = np.asarray(y_prob, dtype=float)
    y_pred_arr = np.asarray(y_pred).astype(int)
    cm = confusion_matrix(y_true_arr, y_pred_arr, labels=[0, 1])
    auc = roc_auc_score(y_true_arr, y_prob_arr) if len(np.unique(y_true_arr)) > 1 else 0.5
    ap = average_precision_score(y_true_arr, y_prob_arr) if len(np.unique(y_true_arr)) > 1 else 0.0
    frac_pos, mean_pred = calibration_curve(y_true_arr, y_prob_arr, n_bins=10, strategy='quantile')
    cal_bins = [
        {'mean_predicted': round(float(mp), 4), 'fraction_positive': round(float(fp), 4)}
        for mp, fp in zip(mean_pred, frac_pos)
    ]
    return {
        'accuracy': round(float(accuracy_score(y_true_arr, y_pred_arr)), 4),
        'roc_auc': round(float(auc), 4),
        'pr_auc': round(float(ap), 4),
        'brier': round(float(brier_score_loss(y_true_arr, y_prob_arr)), 4),
        'log_loss': round(float(log_loss(y_true_arr, np.clip(y_prob_arr, 1e-6, 1 - 1e-6))), 4),
        'confusion_matrix': {
            'tn': int(cm[0, 0]),
            'fp': int(cm[0, 1]),
            'fn': int(cm[1, 0]),
            'tp': int(cm[1, 1]),
        },
        'calibration_curve': cal_bins,
    }


def get_or_create_split_indices(key, n_rows, y_all, test_size=0.2, random_state=42):
    os.makedirs('models', exist_ok=True)
    store = {}
    if os.path.exists(SPLIT_INDEX_PATH):
        try:
            with open(SPLIT_INDEX_PATH) as f:
                store = json.load(f)
        except Exception:
            store = {}

    existing = store.get(key)
    if existing:
        tr_idx = np.array(existing.get('train_idx', []), dtype=int)
        te_idx = np.array(existing.get('test_idx', []), dtype=int)
        if len(tr_idx) + len(te_idx) == int(n_rows):
            return tr_idx, te_idx

    idx = np.arange(n_rows)
    tr_idx, te_idx = train_test_split(
        idx, test_size=test_size, random_state=random_state, stratify=y_all
    )
    store[key] = {'train_idx': tr_idx.tolist(), 'test_idx': te_idx.tolist()}
    with open(SPLIT_INDEX_PATH, 'w') as f:
        json.dump(store, f, indent=2)
    return tr_idx, te_idx


def build_calibrated_model(base_model, method):
    return CalibratedClassifierCV(
        estimator=clone(base_model),
        method=method,
        cv=3,
    )


def train_disease_model(X_tr, X_te, y_tr, y_te, name):
    # Hold out a validation slice from training data so model/calibration/threshold
    # selection never uses the final test split.
    X_fit, X_val, y_fit, y_val = train_test_split(
        X_tr, y_tr, test_size=0.2, random_state=42, stratify=y_tr
    )

    cv = StratifiedKFold(n_splits=4, shuffle=True, random_state=42)
    candidates = build_candidates()
    scored = []
    for label, model in candidates:
        cv_auc = cross_val_score(model, X_fit, y_fit, cv=cv, scoring='roc_auc', n_jobs=1).mean()
        scored.append((label, model, cv_auc))
    xgb_best_model, xgb_cv_auc = train_tuned_xgboost(X_fit, y_fit)
    if xgb_best_model is not None:
        scored.append(('xgboost_tuned', xgb_best_model, xgb_cv_auc))
    scored.sort(key=lambda x: x[2], reverse=True)
    best_label, best_model, best_cv_auc = scored[0]

    # Select calibration strategy + threshold on validation split only.
    evaluated = []
    for method in ['none', 'sigmoid', 'isotonic']:
        if method == 'none':
            mdl = clone(best_model)
            mdl.fit(X_fit, y_fit)
        else:
            mdl = build_calibrated_model(best_model, method)
            mdl.fit(X_fit, y_fit)

        val_prob = mdl.predict_proba(X_val)[:, 1]
        threshold, val_acc = select_threshold(y_val, val_prob)
        val_pred = (val_prob >= threshold).astype(int)
        val_auc = roc_auc_score(y_val, val_prob) if len(np.unique(y_val)) > 1 else 0.5
        val_brier = brier_score_loss(y_val, val_prob)
        val_ll = log_loss(y_val, np.clip(val_prob, 1e-6, 1 - 1e-6))
        evaluated.append((method, threshold, val_acc, val_auc, val_brier, val_ll))

    evaluated.sort(key=lambda x: (x[2], x[3], -x[4]), reverse=True)
    calibration_method, best_threshold, val_acc, val_auc, val_brier, val_ll = evaluated[0]

    # Refit selected strategy on full training split; evaluate once on untouched test split.
    if calibration_method == 'none':
        final_model = clone(best_model)
        final_model.fit(X_tr, y_tr)
    else:
        final_model = build_calibrated_model(best_model, calibration_method)
        final_model.fit(X_tr, y_tr)

    final_prob = final_model.predict_proba(X_te)[:, 1]
    final_pred = (final_prob >= best_threshold).astype(int)
    train_prob = final_model.predict_proba(X_tr)[:, 1]
    train_acc = accuracy_score(y_tr, (train_prob >= best_threshold).astype(int))
    acc = accuracy_score(y_te, final_pred)
    auc = roc_auc_score(y_te, final_prob) if len(np.unique(y_te)) > 1 else 0.5
    brier = brier_score_loss(y_te, final_prob)
    ll = log_loss(y_te, np.clip(final_prob, 1e-6, 1 - 1e-6))
    print(
        f"   {name:<30} model={best_label:<12} th={best_threshold:.2f} "
        f"cal={calibration_method:<8} brier={brier:.4f} "
        f"val_acc={val_acc*100:.1f}% cv_auc={best_cv_auc:.3f} "
        f"acc={acc*100:.1f}% auc={auc:.3f}"
    )
    return (
        final_model, acc, auc, best_label, best_cv_auc, best_threshold, train_acc,
        calibration_method, brier, ll, y_te, final_prob, final_pred
    )

def compute_shap_importance(model, X_sample):
    if shap is None or XGBClassifier is None:
        return None
    try:
        if not isinstance(model, XGBClassifier):
            return None
        explainer = shap.Explainer(model)
        sv = explainer(X_sample)
        abs_mean = np.abs(sv.values).mean(axis=0)
        importance = dict(zip(FEATURE_COLS, abs_mean.tolist()))
        return {k: round(v, 6) for k, v in sorted(importance.items(), key=lambda x: -x[1])}
    except Exception:
        return None

def train():
    print("🧬 Building training datasets…")
    df = generate_dataset(6000)
    print(f"   Synthetic samples: {len(df)}")
    real_X, real_y, real_source = load_real_master_dataset()
    if real_X is not None:
        print(f"   Real master dataset: {len(real_X)} rows from {real_source.get('uci_dir')}")
        if real_source.get('hf_support_path'):
            print(f"   HF support dataset: {real_source.get('hf_support_rows')} rows from {real_source.get('hf_support_path')}")
        if real_source.get('saheart_path'):
            print(f"   SAheart source detected: {real_source.get('saheart_path')}")
    else:
        print("   Real master dataset not found; using synthetic master target.")

    base_X = df[FEATURE_COLS].reset_index(drop=True)
    targets = {
        'cad': df['cad'].reset_index(drop=True),
        'hf': df['hf'].reset_index(drop=True),
        'arr': df['arr'].reset_index(drop=True),
        'mi': df['mi'].reset_index(drop=True),
    }

    master_blend = {'mode': 'synthetic_only'}
    if real_X is not None:
        synth_idx = base_X.sample(n=min(len(base_X), int(len(real_X) * MASTER_SYNTH_FACTOR)), random_state=42).index
        synth_master_X = base_X.loc[synth_idx].reset_index(drop=True)
        synth_master_y = df.loc[synth_idx, 'target'].reset_index(drop=True)
        master_X = pd.concat([real_X.reset_index(drop=True), synth_master_X], axis=0, ignore_index=True)
        master_y = pd.concat([real_y.reset_index(drop=True), synth_master_y], axis=0, ignore_index=True)
        master_blend = {
            'mode': 'hybrid_real_synthetic',
            'real_rows': int(len(real_X)),
            'synthetic_rows': int(len(synth_master_X)),
            'real_fraction': round(float(len(real_X) / len(master_X)), 3),
            'synth_factor': MASTER_SYNTH_FACTOR,
        }
    else:
        master_X = base_X
        master_y = df['target'].reset_index(drop=True)
    targets['master'] = master_y

    os.makedirs('models', exist_ok=True)
    legacy_scaler = None

    print("\n🤖 Training models (LogReg / RF / XGBoost / Ensemble candidates)…")
    models_meta = {}
    eval_report = {
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'feature_count': len(FEATURE_COLS),
        'models': {},
    }
    master_train_Xs = None
    master_train_y = None
    master_test_prob = None
    master_test_true = None
    for key in ['master', 'cad', 'hf', 'arr', 'mi']:
        X_all = master_X if key == 'master' else base_X
        y_all = targets[key]
        tr_idx, te_idx = get_or_create_split_indices(key, len(X_all), y_all, test_size=0.2, random_state=42)
        X_tr = X_all.iloc[tr_idx].reset_index(drop=True)
        X_te = X_all.iloc[te_idx].reset_index(drop=True)
        y_tr = y_all.iloc[tr_idx].reset_index(drop=True)
        y_te = y_all.iloc[te_idx].reset_index(drop=True)
        scaler = StandardScaler()
        scaler.fit(X_tr)
        X_tr_s = pd.DataFrame(scaler.transform(X_tr), columns=FEATURE_COLS)
        X_te_s = pd.DataFrame(scaler.transform(X_te), columns=FEATURE_COLS)
        (
            clf, acc, auc, model_name, cv_auc, threshold, train_acc,
            calibration_method, brier, ll, y_te_out, prob_out, pred_out
        ) = train_disease_model(X_tr_s, X_te_s, y_tr, y_te, key)
        joblib.dump(clf, f'models/{key}_model.pkl')
        joblib.dump(scaler, f'models/{key}_scaler.pkl')
        models_meta[key] = {
            'accuracy': round(acc*100, 1),
            'auc': round(auc, 3),
            'train_accuracy': round(float(train_acc)*100, 1),
            'cv_auc': round(float(cv_auc), 3),
            'selected_model': model_name,
            'calibration': calibration_method,
            'brier': round(float(brier), 4),
            'log_loss': round(float(ll), 4),
            'threshold': round(float(threshold), 3),
        }
        eval_report['models'][key] = build_eval_metrics(y_te_out, prob_out, pred_out)
        eval_report['models'][key]['threshold'] = round(float(threshold), 4)
        eval_report['models'][key]['selected_model'] = model_name
        eval_report['models'][key]['calibration'] = calibration_method
        shap_imp = compute_shap_importance(clf, X_te_s.head(200))
        if shap_imp is not None:
            models_meta[key]['shap_feature_importance'] = shap_imp
        if key == 'master':
            legacy_scaler = scaler
            master_train_Xs = X_tr_s
            master_train_y = y_tr
            master_test_prob = np.asarray(prob_out, dtype=float)
            master_test_true = np.asarray(y_te_out).astype(int)

    # Backward-compatible single scaler artifact (master model scaler).
    if legacy_scaler is not None:
        joblib.dump(legacy_scaler, 'models/scaler.pkl')

    # Feature importances from master RF
    rf_sub = RandomForestClassifier(n_estimators=200, max_depth=9, random_state=42, n_jobs=-1)
    rf_sub.fit(master_train_Xs, master_train_y)
    importances = dict(zip(FEATURE_COLS, rf_sub.feature_importances_.tolist()))

    meta = {
        'features': FEATURE_COLS,
        'models': models_meta,
        'feature_importances': {k: round(v,4) for k,v in sorted(importances.items(), key=lambda x:-x[1])},
        'disease_prevalence': {k: float(v.mean().round(3)) for k,v in targets.items()},
        'master_training_source': real_source if real_source else 'synthetic',
        'master_training_blend': master_blend,
        'split_index_path': SPLIT_INDEX_PATH,
    }
    with open('models/model_meta.json','w') as f:
        json.dump(meta, f, indent=2)

    if master_test_prob is not None and master_test_true is not None:
        tier_counts = {'LOW': 0, 'MODERATE': 0, 'HIGH': 0, 'CRITICAL': 0}
        for p in master_test_prob:
            tier_counts[risk_tier_label(float(p) * 100.0)] += 1
        total = max(1, int(len(master_test_prob)))
        eval_report['master_risk_tier_distribution'] = {
            k: {'count': int(v), 'fraction': round(float(v / total), 4)}
            for k, v in tier_counts.items()
        }
        eval_report['master_positive_rate'] = round(float(master_test_true.mean()), 4)
    eval_report['master_training_source'] = meta['master_training_source']
    eval_report['master_training_blend'] = meta['master_training_blend']
    with open('models/eval_report.json', 'w') as f:
        json.dump(eval_report, f, indent=2)

    print(f"\n✅ All models saved. Master accuracy: {models_meta['master']['accuracy']}%")
    return meta

if __name__ == '__main__':
    train()
