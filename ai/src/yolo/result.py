"""알약 탐지 모델 성능 확인.

터미널에서 단독 실행도 가능:
    python result.py yolo11s
    python result.py --all
    python result.py --model-name yolo26l confusion
    python result.py --model-name yolo26l grid-search --save-interface
    python result.py --model-name yolo26l class-scores --conf 0.15 --iou 0.5
"""

import argparse
import itertools
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

YOLO_DIR = Path(__file__).parent
RUNS_DIR = YOLO_DIR / "runs/detect"

METRIC_COLUMNS = {
    "mAP50": "metrics/mAP50(B)",
    "mAP50-95": "metrics/mAP50-95(B)",
    "recall": "metrics/recall(B)",
}

DATASET_PATHS = {
    "v1": "../../data/processed/shared/dataset.yaml",
    "v2": "../../data/processed/shared_v2/dataset.yaml",
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
        p
        for p in RUNS_DIR.iterdir()
        if p.is_dir() and pattern.match(p.name) and (p / "results.csv").exists()
    )


def find_all_runs() -> list[Path]:
    """runs/detect 하위의 results.csv가 있는 모든 run 폴더를 찾습니다."""
    if not RUNS_DIR.exists():
        return []
    return sorted(p.parent for p in RUNS_DIR.rglob("results.csv"))


def find_best_weights(model_name: str) -> Path | None:
    """선택된 모델의 가장 최근 학습 결과에서 best.pt 경로를 반환합니다.

    confusion/grid-search/class-scores처럼 단일 run의 가중치가 필요한
    분석 함수들이 사용합니다 (find_runs_for_model은 여러 run을 비교할 때 사용).
    """
    if not RUNS_DIR.exists():
        return None
    candidates = sorted(
        [
            d
            for d in RUNS_DIR.glob(f"{model_name}*")
            if (d / "weights/best.pt").exists()
        ],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return (candidates[0] / "weights/best.pt") if candidates else None


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
    result_df = result_df.sort_values(by="mAP50-95", ascending=False).reset_index(
        drop=True
    )

    print(
        f"\n {'model':<20} {'epoch':>12} {'mAP50':>13} {'mAP50-95':>10} {'recall':>9}"
    )
    for _, row in result_df.iterrows():
        print(
            f"{row['run']:<25} "
            f"{row['best_epoch']:>4}/{row['total_epochs']:<5} "
            f"{row['mAP50']:>10} "
            f"{row['mAP50-95']:>10} "
            f"{row['recall']:>10}"
        )

    best = result_df.iloc[0]
    print(
        f"\n최고 성능: {best['run']} | mAP50  {best['mAP50']} | mAP50-95  {best['mAP50-95']} | recall  {best['recall']}"
    )

    return result_df


def plot_normalized_confusion_matrix(weights_path, data_yaml, figsize=(20, 18)) -> None:
    """정규화된 confusion matrix를 그리고, 가장 헷갈리는 클래스 쌍 상위 10개를 출력합니다.

    Args:
        weights_path: 평가에 사용할 가중치(best.pt) 경로.
        data_yaml: 평가에 사용할 dataset.yaml 경로.
        figsize: 그래프 크기.
    """
    from ultralytics import YOLO

    model = YOLO(weights_path)
    metrics = model.val(data=str(data_yaml), plots=True)

    cm = metrics.confusion_matrix.matrix
    if cm.sum() == 0:
        raise RuntimeError(
            "confusion matrix가 비어 있습니다. weights_path/data_yaml 경로를 확인하세요."
        )

    col_sums = cm.sum(axis=0, keepdims=True)
    col_sums[col_sums == 0] = 1
    cm_normalized = cm / col_sums

    dataset_config = load_config(data_yaml)
    class_names = list(dataset_config["names"].values()) + ["background"]

    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(cm_normalized, cmap="Blues", vmin=0, vmax=1)

    ax.set_xticks(range(len(class_names)))
    ax.set_yticks(range(len(class_names)))
    ax.set_xticklabels(class_names, rotation=90, fontsize=7)
    ax.set_yticklabels(class_names, fontsize=7)
    ax.set_xlabel("True")
    ax.set_ylabel("Predicted")
    ax.set_title("Normalized Confusion Matrix")

    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    plt.show()

    off_diagonal = cm_normalized.copy()
    np.fill_diagonal(off_diagonal, 0)
    top_confusions = []
    n = len(class_names)
    for i in range(n):
        for j in range(n):
            if i != j and off_diagonal[i, j] > 0:
                top_confusions.append(
                    (off_diagonal[i, j], class_names[j], class_names[i])
                )
    top_confusions.sort(reverse=True)

    print("\n가장 많이 헷갈리는 클래스 쌍 (실제 -> 예측, 비율):")
    for score, true_name, pred_name in top_confusions[:10]:
        print(f"  {true_name} -> {pred_name}: {score:.2%}")


def grid_search_thresholds(
    weights_path, data_yaml, conf_values=None, iou_values=None
) -> pd.DataFrame:
    """conf/iou 조합별로 val을 돌려 mAP50-95 기준 내림차순으로 정렬한 결과를 반환합니다.

    Args:
        weights_path: 평가에 사용할 가중치(best.pt) 경로.
        data_yaml: 평가에 사용할 dataset.yaml 경로.
        conf_values: 시도할 confidence threshold 목록.
        iou_values: 시도할 NMS IoU threshold 목록.
    """
    from ultralytics import YOLO

    conf_values = conf_values or [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
    iou_values = iou_values or [0.4, 0.5, 0.6, 0.7]

    model = YOLO(weights_path)
    grid_results = []

    for conf, iou in itertools.product(conf_values, iou_values):
        metrics = model.val(
            data=str(data_yaml), conf=conf, iou=iou, plots=False, verbose=False
        )
        grid_results.append(
            {
                "conf": conf,
                "iou": iou,
                "mAP50": metrics.box.map50,
                "mAP50-95": metrics.box.map,
                "recall": metrics.box.mr,
            }
        )

    grid_df = pd.DataFrame(grid_results).sort_values("mAP50-95", ascending=False)
    print(grid_df.to_string(index=False))
    print("\n최고 mAP50-95 조합:")
    print(grid_df.iloc[0])
    return grid_df


def save_interface_config(conf: float, iou: float):
    """그리드서치 최적 conf/iou를 interface.yaml에 반영합니다 (다른 키는 그대로 유지)."""
    interface_path = YOLO_DIR / "interface.yaml"
    config = load_config(interface_path)
    config["conf"] = conf
    config["iou"] = iou
    with open(interface_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    print(f"interface.yaml 갱신 완료: conf={conf}, iou={iou}")


def class_scores_below(
    weights_path, data_yaml, conf: float, iou: float, top_n: int = 15
) -> pd.DataFrame:
    """클래스별 mAP50-95를 낮은 순으로 정렬해 상위 top_n개를 반환합니다."""
    from ultralytics import YOLO

    class_names_dict = load_config(data_yaml)["names"]

    model = YOLO(weights_path)
    metrics = model.val(data=str(data_yaml), conf=conf, iou=iou, plots=False)

    class_scores = []
    for cls_idx, score in enumerate(metrics.box.maps):
        class_name = class_names_dict.get(cls_idx, f"class_{cls_idx}")
        class_scores.append({"class": class_name, "mAP50-95": score})

    class_df = pd.DataFrame(class_scores).sort_values("mAP50-95")
    print(f"mAP50-95 낮은 순 (하위 {top_n}개):")
    print(class_df.head(top_n).to_string(index=False))
    return class_df


def main(model_name: str | None = None):
    """model_name이 주어지면 해당 모델의 run만, 없으면 전체 run을 비교합니다."""
    run_dirs = find_runs_for_model(model_name) if model_name else find_all_runs()
    show_results(run_dirs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="YOLO 학습 결과 확인 (기본 지표 비교 + 심화 분석)"
    )
    parser.add_argument(
        "model_name",
        nargs="?",
        default=None,
        help="확인할 모델의 yaml 파일명 (예: yolo11s). 서브커맨드 없이 쓰면 기본 지표(mAP/recall) 비교",
    )
    parser.add_argument(
        "--all", action="store_true", help="모든 모델의 run을 함께 비교"
    )
    parser.add_argument(
        "--dataset-version",
        default="v1",
        help='confusion/grid-search/class-scores에서 사용할 데이터셋 버전 ("v1" 또는 "v2")',
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("confusion", help="정규화 confusion matrix를 그립니다.")

    grid_parser = sub.add_parser(
        "grid-search", help="conf/iou 그리드서치를 실행합니다 (기본 6x4=24회)."
    )
    grid_parser.add_argument(
        "--save-interface",
        action="store_true",
        help="최적 조합을 interface.yaml에 저장합니다.",
    )

    class_parser = sub.add_parser(
        "class-scores", help="클래스별 mAP50-95를 낮은 순으로 확인합니다."
    )
    class_parser.add_argument("--conf", type=float, required=True)
    class_parser.add_argument("--iou", type=float, required=True)

    args = parser.parse_args()

    if args.command in ("confusion", "grid-search", "class-scores"):
        target_model_name = args.model_name or "yolo26l"
        data_yaml = (YOLO_DIR / DATASET_PATHS[args.dataset_version]).resolve()

        best_pt = find_best_weights(target_model_name)
        if best_pt is None:
            print(
                f"[오류] '{target_model_name}'의 학습된 가중치(best.pt)를 찾을 수 없습니다."
            )
            print("먼저 학습(train)을 실행하세요.")
        elif args.command == "confusion":
            plot_normalized_confusion_matrix(best_pt, data_yaml)
        elif args.command == "grid-search":
            grid_df = grid_search_thresholds(best_pt, data_yaml)
            if args.save_interface:
                best_row = grid_df.iloc[0]
                save_interface_config(
                    conf=float(best_row["conf"]), iou=float(best_row["iou"])
                )
        elif args.command == "class-scores":
            class_scores_below(best_pt, data_yaml, conf=args.conf, iou=args.iou)
    else:
        main(model_name=None if args.all else args.model_name)
