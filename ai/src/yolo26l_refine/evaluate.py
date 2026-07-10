# ============================================================
# 파일 역할: evaluate.py
# train.py로 학습이 끝난 뒤 결과를 확인하는 파일.
#   - metrics       : mAP50 / mAP50-95 / recall 숫자 확인
#   - confusion      : confusion matrix 그림 + 헷갈리는 클래스 쌍 확인
#   - grid-search    : conf/iou 값을 바꿔가며 최적 조합 탐색
#   - class-scores   : 어떤 클래스가 점수를 깎아먹는지 확인
# 여기서 찾은 헷갈리는 클래스 쌍을 hard_negative.py에 넘겨서 보강 학습함.
# ============================================================
"""학습 결과 확인: mAP 지표 / confusion matrix / conf·iou 튜닝 / 클래스별 성능.

사용 예:
    python evaluate.py metrics
    python evaluate.py confusion
    python evaluate.py grid-search --save-interface
    python evaluate.py class-scores --conf 0.15 --iou 0.5
    python evaluate.py --model-name yolo26l_hardneg confusion
"""

import argparse
import itertools

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from ultralytics import YOLO

from common import DATASET_YAML, YOLO_DIR, find_latest_run, load_config


def print_best_metrics(model_name: str) -> None:
    """results.csv에서 mAP50-95가 가장 좋았던 epoch의 지표를 출력합니다."""
    latest_run = find_latest_run(model_name)
    df = pd.read_csv(latest_run / "results.csv")
    df.columns = df.columns.str.strip()
    best = df.loc[df["metrics/mAP50-95(B)"].idxmax()]
    print(
        f"{latest_run.name}: mAP50={best['metrics/mAP50(B)']:.4f} "
        f"mAP50-95={best['metrics/mAP50-95(B)']:.4f} recall={best['metrics/recall(B)']:.4f}"
    )


def plot_normalized_confusion_matrix(weights_path, data_yaml=DATASET_YAML, figsize=(20, 18)) -> None:
    """정규화된 confusion matrix를 그리고, 가장 헷갈리는 클래스 쌍 상위 10개를 출력합니다.

    Args:
        weights_path: 평가에 사용할 가중치(best.pt) 경로.
        data_yaml: 평가에 사용할 dataset.yaml 경로.
        figsize: 그래프 크기.
    """
    model = YOLO(weights_path)
    metrics = model.val(data=str(data_yaml), plots=True)

    cm = metrics.confusion_matrix.matrix
    if cm.sum() == 0:
        raise RuntimeError("confusion matrix가 비어 있습니다. weights_path/data_yaml 경로를 확인하세요.")

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
                top_confusions.append((off_diagonal[i, j], class_names[j], class_names[i]))
    top_confusions.sort(reverse=True)

    print("\n가장 많이 헷갈리는 클래스 쌍 (실제 -> 예측, 비율):")
    for score, true_name, pred_name in top_confusions[:10]:
        print(f"  {true_name} -> {pred_name}: {score:.2%}")


def grid_search_thresholds(weights_path, conf_values=None, iou_values=None) -> pd.DataFrame:
    """conf/iou 조합별로 val을 돌려 mAP50-95 기준 내림차순으로 정렬한 결과를 반환합니다.

    Args:
        weights_path: 평가에 사용할 가중치(best.pt) 경로.
        conf_values: 시도할 confidence threshold 목록.
        iou_values: 시도할 NMS IoU threshold 목록.
    """
    conf_values = conf_values or [0.05, 0.1, 0.15, 0.2, 0.25, 0.3]
    iou_values = iou_values or [0.4, 0.5, 0.6, 0.7]

    model = YOLO(weights_path)
    grid_results = []

    for conf, iou in itertools.product(conf_values, iou_values):
        metrics = model.val(data=str(DATASET_YAML), conf=conf, iou=iou, plots=False, verbose=False)
        grid_results.append({
            "conf": conf,
            "iou": iou,
            "mAP50": metrics.box.map50,
            "mAP50-95": metrics.box.map,
            "recall": metrics.box.mr,
        })

    grid_df = pd.DataFrame(grid_results).sort_values("mAP50-95", ascending=False)
    print(grid_df.to_string(index=False))
    print("\n최고 mAP50-95 조합:")
    print(grid_df.iloc[0])
    return grid_df


def save_interface_config(conf: float, iou: float) -> None:
    """그리드서치 최적 conf/iou를 config/interface.yaml에 반영합니다 (imgsz는 유지)."""
    interface_path = YOLO_DIR / "config" / "interface.yaml"
    config = load_config(interface_path)
    config["conf"] = conf
    config["iou"] = iou
    with open(interface_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True)
    print(f"config/interface.yaml 갱신 완료: conf={conf}, iou={iou}")


def class_scores_below(weights_path, conf: float, iou: float, top_n: int = 15) -> pd.DataFrame:
    """클래스별 mAP50-95를 낮은 순으로 정렬해 상위 top_n개를 반환합니다."""
    class_names_dict = load_config(DATASET_YAML)["names"]

    model = YOLO(weights_path)
    metrics = model.val(data=str(DATASET_YAML), conf=conf, iou=iou, plots=False)

    class_scores = []
    for cls_idx, score in enumerate(metrics.box.maps):
        class_name = class_names_dict.get(cls_idx, f"class_{cls_idx}")
        class_scores.append({"class": class_name, "mAP50-95": score})

    class_df = pd.DataFrame(class_scores).sort_values("mAP50-95")
    print(f"mAP50-95 낮은 순 (하위 {top_n}개):")
    print(class_df.head(top_n).to_string(index=False))
    return class_df


def main() -> None:
    parser = argparse.ArgumentParser(description="학습 결과 확인 (metrics / confusion matrix / threshold 튜닝)")
    parser.add_argument("--model-name", default="yolo26l", help="find_latest_run에 쓸 run 이름 접두사")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("metrics", help="가장 좋았던 epoch의 mAP50 / mAP50-95 / recall을 출력합니다.")
    sub.add_parser("confusion", help="정규화 confusion matrix를 그립니다.")

    grid_parser = sub.add_parser("grid-search", help="conf/iou 그리드서치를 실행합니다 (기본 6x4=24회).")
    grid_parser.add_argument("--save-interface", action="store_true", help="최적 조합을 config/interface.yaml에 저장합니다.")

    class_parser = sub.add_parser("class-scores", help="클래스별 mAP50-95를 낮은 순으로 확인합니다.")
    class_parser.add_argument("--conf", type=float, required=True)
    class_parser.add_argument("--iou", type=float, required=True)

    args = parser.parse_args()
    latest_run = find_latest_run(args.model_name)
    latest_weights = latest_run / "weights" / "best.pt"

    if args.command == "metrics":
        print_best_metrics(args.model_name)
    elif args.command == "confusion":
        plot_normalized_confusion_matrix(latest_weights)
    elif args.command == "grid-search":
        grid_df = grid_search_thresholds(latest_weights)
        if args.save_interface:
            best_row = grid_df.iloc[0]
            save_interface_config(conf=float(best_row["conf"]), iou=float(best_row["iou"]))
    elif args.command == "class-scores":
        class_scores_below(latest_weights, conf=args.conf, iou=args.iou)


if __name__ == "__main__":
    main()
