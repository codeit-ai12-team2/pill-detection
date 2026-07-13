"""학습 결과 확인: confusion matrix / conf·iou 튜닝 / 클래스별 성능.

mAP50 / mAP50-95 / recall 같은 기본 지표 확인은 result.py를 사용하세요.
이 스크립트는 result.py에 없는 세 가지 분석 기능만 제공합니다.

사용 예:
    python evaluate.py confusion
    python evaluate.py grid-search --save-interface
    python evaluate.py class-scores --conf 0.15 --iou 0.5
    python evaluate.py --model-name yolo26l_hardneg confusion
"""

import argparse
import itertools
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from ultralytics import YOLO

YOLO_DIR = Path(__file__).parent

DATASET_PATHS = {
    "v1": "../../data/processed/shared/dataset.yaml",
    "v2": "../../data/processed/shared_v2/dataset.yaml",
}


def load_config(config_path):
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_best_weights(model_name: str):
    """선택된 모델의 가장 최근 학습 결과에서 best.pt 경로를 반환합니다."""
    runs_dir = YOLO_DIR / "runs/detect"
    if not runs_dir.exists():
        return None
    candidates = sorted(
        [
            d
            for d in runs_dir.glob(f"{model_name}*")
            if (d / "weights/best.pt").exists()
        ],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return (candidates[0] / "weights/best.pt") if candidates else None


def plot_normalized_confusion_matrix(weights_path, data_yaml, figsize=(20, 18)) -> None:
    """정규화된 confusion matrix를 그리고, 가장 헷갈리는 클래스 상위 10개를 출력합니다.

    Args:
        weights_path: 평가에 사용할 가중치(best.pt) 경로.
        data_yaml: 평가에 사용할 dataset.yaml 경로.
        figsize: 그래프 크기.
    """
    model = YOLO(weights_path)
    metrics = model.val(data=str(data_yaml), plots=True)

    cm = metrics.confusion_matrix.matrix
    if cm.sum() == 0:
        raise RuntimeError("confusion matrix가 비어 있습니다.")

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
    """그리드서치 최적 conf/iou를 interface.yaml에 반영합니다."""
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


def main():
    parser = argparse.ArgumentParser(description="학습 결과 심화 분석")
    parser.add_argument(
        "--model-name", default="yolo26l", help="find_best_weights에 쓸 run 이름 접두사"
    )
    parser.add_argument("--dataset-version", default="v1", help='"v1" 또는 "v2"')
    sub = parser.add_subparsers(dest="command", required=True)

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

    data_yaml = (YOLO_DIR / DATASET_PATHS[args.dataset_version]).resolve()

    best_pt = find_best_weights(args.model_name)
    if best_pt is None:
        print(
            f"[오류] '{args.model_name}'의 학습된 가중치(best.pt)를 찾을 수 없습니다."
        )
        print("먼저 학습(train)을 실행하세요.")
        return

    if args.command == "confusion":
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


if __name__ == "__main__":
    main()
