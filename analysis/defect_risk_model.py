import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score, confusion_matrix, precision_recall_curve,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data_generation"))
from generate_defects import build_station_part_lookup
from common import load_config

from db_utils import get_connection, query, save_analysis_output

def build_feature_table(conn) -> pd.DataFrame:
    print("  Loading raw tables ...")
    station_ops = query("SELECT * FROM fact_station_operation", conn)
    units = query("SELECT unit_id, model_id, trim_id FROM fact_production_unit", conn)
    dim_worker = query("SELECT worker_id, skill_level FROM dim_worker", conn)
    dim_shift = query("SELECT shift_id, shift_name FROM dim_shift", conn)
    dim_workstation = query("SELECT station_id, station_type FROM dim_workstation", conn)
    bom = query("SELECT * FROM bridge_model_trim_bom", conn)
    dim_part = query("SELECT * FROM dim_part", conn)
    defects = query("SELECT operation_id FROM fact_defect", conn)

    config = load_config()
    part_tied_categories = config["defects"]["part_tied_station_categories"]

    print("  Rebuilding station->part lookup (same logic as generation) ...")
    station_part_lookup = build_station_part_lookup(bom, dim_part, part_tied_categories)

    print("  Joining features ...")
    df = station_ops.merge(units, on="unit_id", how="left")
    df = df.merge(dim_worker, on="worker_id", how="left")
    df = df.merge(dim_shift, on="shift_id", how="left")
    df = df.merge(dim_workstation, on="station_id", how="left")
    df["part_category"] = df["station_type"].map(part_tied_categories)
    df = df.merge(station_part_lookup, on=["model_id", "trim_id", "part_category"], how="left")

    df["downtime_occurred"] = (df["downtime_minutes"] > 0).astype(int)
    df["is_part_tied"] = df["part_category"].notna().astype(int)

    dim_supplier = query("SELECT supplier_id, reliability_score FROM dim_supplier", conn)
    df = df.merge(dim_supplier, left_on="primary_supplier_id", right_on="supplier_id", how="left")

    df["reliability_score"] = df["reliability_score"].fillna(100)
    df["part_complexity_score"] = df["part_complexity_score"].fillna(0)

    df["defect_occurred"] = df["operation_id"].isin(defects["operation_id"]).astype(int)

    return df

def prepare_xy(df: pd.DataFrame):
    feature_cols_numeric = ["downtime_occurred", "is_part_tied", "reliability_score", "part_complexity_score"]
    feature_cols_categorical = ["station_type", "skill_level", "shift_name"]

    X = pd.get_dummies(df[feature_cols_numeric + feature_cols_categorical],
                        columns=feature_cols_categorical, drop_first=True)
    y = df["defect_occurred"]
    return X, y

def find_best_f1_threshold(y_test, y_proba):
    precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)
    f1_scores = 2 * precisions * recalls / (precisions + recalls + 1e-12)
    best_idx = np.argmax(f1_scores[:-1])
    return thresholds[best_idx], precisions[best_idx], recalls[best_idx], f1_scores[best_idx]


def evaluate_model(name, model, X_test, y_test) -> dict:
    y_proba = model.predict_proba(X_test)[:, 1]

    roc_auc = roc_auc_score(y_test, y_proba)
    pr_auc = average_precision_score(y_test, y_proba)

    y_pred_default = (y_proba >= 0.5).astype(int)
    default_metrics = {
        "precision_at_0.5": round(precision_score(y_test, y_pred_default, zero_division=0), 4),
        "recall_at_0.5": round(recall_score(y_test, y_pred_default, zero_division=0), 4),
    }

    best_thresh, best_p, best_r, best_f1 = find_best_f1_threshold(y_test, y_proba)
    y_pred_best = (y_proba >= best_thresh).astype(int)

    metrics = {
        "model": name,
        "roc_auc": round(roc_auc, 4),
        "pr_auc": round(pr_auc, 4),
        **default_metrics,
        "best_threshold": round(float(best_thresh), 4),
        "precision_at_best_f1": round(float(best_p), 4),
        "recall_at_best_f1": round(float(best_r), 4),
        "f1_at_best_threshold": round(float(best_f1), 4),
        "accuracy_at_best_threshold": round(accuracy_score(y_test, y_pred_best), 4),
    }

    cm = confusion_matrix(y_test, y_pred_best)
    print(f"\n{name} confusion matrix at best-F1 threshold ({best_thresh:.3f}):")
    print(cm)
    return metrics, y_proba

def main():
    conn = get_connection()
    print("Building feature table ...")
    df = build_feature_table(conn)
    print(f"  {len(df):,} operations | positive rate = {df['defect_occurred'].mean()*100:.3f}%")

    X, y = prepare_xy(df)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    print("\nTraining Logistic Regression ...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    logreg = LogisticRegression(class_weight="balanced", max_iter=1000)
    logreg.fit(X_train_scaled, y_train)
    logreg_metrics, _ = evaluate_model("Logistic Regression", logreg, X_test_scaled, y_test)

    print("\nTraining Random Forest ...")
    rf = RandomForestClassifier(n_estimators=200, max_depth=10, class_weight="balanced_subsample", random_state=42, n_jobs=-1)
    rf.fit(X_train, y_train)
    rf_metrics, rf_proba = evaluate_model("Random Forest", rf, X_test, y_test)

    comparison = pd.DataFrame([logreg_metrics, rf_metrics])
    path1 = save_analysis_output(comparison, "defect_model_comparison")
    print(f"\nModel comparison:\n{comparison.to_string(index=False)}")
    print(f"  -> {path1}")

    importance = pd.DataFrame({"feature": X.columns, "importance": rf.feature_importances_}).sort_values("importance", ascending=False)
    path2 = save_analysis_output(importance, "defect_feature_importance")
    print(f"\nTop 10 features:\n{importance.head(10).to_string(index=False)}")
    print(f"  -> {path2}")

    df_test = df.loc[X_test.index].copy()
    df_test["predicted_risk"] = rf_proba
    high_risk = (df_test[df_test["is_part_tied"] == 1]
                 .groupby(["station_type", "part_category"])
                 .agg(avg_predicted_risk=("predicted_risk", "mean"),
                      n_operations=("predicted_risk", "size"),
                      actual_defect_rate=("defect_occurred", "mean"))
                 .reset_index().sort_values("avg_predicted_risk", ascending=False))
    high_risk["avg_predicted_risk"] = round(high_risk["avg_predicted_risk"], 4)
    high_risk["actual_defect_rate"] = round(high_risk["actual_defect_rate"], 4)
    path3 = save_analysis_output(high_risk, "high_risk_combinations")
    print(f"\n{high_risk.to_string(index=False)}")
    print(f"  -> {path3}")

    conn.close()
    return comparison, importance, high_risk


if __name__ == "__main__":
    main()
