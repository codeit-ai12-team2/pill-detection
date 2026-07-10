"""알약 탐지 모델 성능 확인.

터미널에서 단독 실행도 가능:
    python result.py yolo11s
    python result.py --all
"""

import argparse
from pathlib import Path

import pandas as pd
import re
import yaml

YOLO_DIR = Path(__file__).parent
RUNS_DIR = YOLO_DIR / "runs/detect"

METRIC_COLUMNS = {
    "mAP50": "metrics/mAP50(B)",
    "mAP50-95": "metrics/mAP50-95(B)",
    "recall": "metrics/recall(B)",
}


def load_config(config_path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_runs_for_model(model_name: str) -> list[Path]:
    """model_name.yaml의 name 값을 기준으로 runs/detect/{name}* 폴더 탐지

    같은 name으로 여러 번 학습하면 Ultralytics가 name-2, name-3 ... 로
    번호를 붙이므로, 접두사가 일치하는 모든 run 탐지
    """
    config = load_config(YOLO_DIR / f"{model_name}.yaml")
    run_name = config["name"]

    if not RUNS_DIR.exists():
        return []
    
    pattern = re.compile(rf"^{re.escape(run_name)}(-?\d+)?$")

    return sorted(
        p for p in RUNS_DIR.iterdir()
        if p.is_dir() and pattern.match(p.name) and (p / "results.csv").exists()
    )


def find_all_runs() -> list[Path]:
    """runs/detect 하위의 results.csv가 있는 모든 run 폴더를 찾습니다."""
    if not RUNS_DIR.exists():
        return []
    return sorted(p.parent for p in RUNS_DIR.rglob("results.csv"))


def summarize_run(run_dir: Path) -> dict | None:
    """하나의 run에서 mAP50-95 기준 best epoch 정보 추출"""
    csv_path = run_dir / "results.csv"
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()

    map50_col = METRIC_COLUMNS["mAP50"]
    map95_col = METRIC_COLUMNS["mAP50-95"]
    recall_col = METRIC_COLUMNS["recall"]

    if map95_col not in df.columns:
        print(f"[skip] {csv_path} : '{map95_col}' 컬럼 없음")
        return None

    best_row = df.loc[df[map95_col].idxmax()]

    return {
        "run": run_dir.name,
        "best_epoch": int(best_row["epoch"]),
        "total_epochs": int(df["epoch"].max()),
        "mAP50": round(best_row[map50_col], 4),
        "mAP50-95": round(best_row[map95_col], 4),
        "recall": round(best_row[recall_col], 4),
    }


def show_results(run_dirs: list[Path]) -> pd.DataFrame:
    """run 목록의 결과를 요약해서 출력하고 DataFrame으로 반환"""
    if not run_dirs:
        print("결과를 찾지 못했습니다.")
        return pd.DataFrame()

    summaries = [summarize_run(d) for d in run_dirs]
    summaries = [s for s in summaries if s is not None]

    result_df = pd.DataFrame(summaries)
    result_df = result_df.sort_values(by="mAP50-95", ascending=False).reset_index(drop=True)

    print(f"\n {'model':<20} {'epoch':>12} {'mAP50':>13} {'mAP50-95':>10} {'recall':>9}")
    for _, row in result_df.iterrows():
        print(
            f"{row['run']:<25} "
            f"{row['best_epoch']:>4}/{row['total_epochs']:<5} "
            f"{row['mAP50']:>10} "
            f"{row['mAP50-95']:>10} "
            f"{row['recall']:>10}"
        )

    best = result_df.iloc[0]
    print(f"\n최고 성능: {best['run']} | mAP50  {best['mAP50']} | mAP50-95  {best['mAP50-95']} | recall  {best['recall']}")

    return result_df


def main(model_name: str | None = None):
    """model_name이 주어지면 해당 모델의 run만, 없으면 전체 run을 비교합니다."""
    run_dirs = find_runs_for_model(model_name) if model_name else find_all_runs()
    show_results(run_dirs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO 학습 결과 성능 확인")
    parser.add_argument("model_name", nargs="?", default=None, help="확인할 모델의 yaml 파일명 (예: yolo11s)")
    parser.add_argument("--all", action="store_true", help="모든 모델의 run을 함께 비교")
    args = parser.parse_args()

    main(model_name=None if args.all else args.model_name)