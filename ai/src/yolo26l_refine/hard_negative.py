# ============================================================
# 파일 역할: hard_negative.py
# evaluate.py confusion에서 찾은 "계속 헷갈리는 클래스 쌍"만 따로 모아서
# 추가로 짧게 fine-tuning하는 파일. train.py를 다시 통째로 돌리는 게 아니라
# 기존 best.pt에서 "이어서" 낮은 lr로 조금만 더 학습하는 방식.
#   - build     : 헷갈리는 클래스가 포함된 train 이미지만 추출
#   - finetune  : 추출한 데이터로 추가 학습
# val은 절대 건드리지 않음 (평가 신뢰성 유지 목적).
# ============================================================
"""가장 헷갈리는 클래스 쌍에 대한 Hard Negative Mining 및 추가 Fine-tuning.

val은 절대 건드리지 않습니다 (섞이면 confusion matrix 평가가 "이미 본 데이터"를
다시 채점하는 셈이 되어 leakage가 재발합니다). train에서만 대상 클래스가 포함된
이미지를 추출해 낮은 lr로 짧게 추가 학습합니다.

사용 예:
    python hard_negative.py build --classes "리바로정 4mg" "가바토파정 100mg"
    python hard_negative.py finetune --base-model-name yolo26l
"""

import argparse
import shutil
from pathlib import Path

import albumentations as A
import cv2
import yaml
from ultralytics import YOLO

from common import (
    DATASET_YAML,
    IMAGES_DIR,
    LABELS_DIR,
    OUTPUT_DIR,
    find_latest_run,
    get_device,
    load_class_names,
    load_config,
)

HARDNEG_DIR = OUTPUT_DIR / "hardneg"


def extract_hard_negative_samples(target_class_names: list) -> Path:
    """지정한 클래스가 포함된 train 이미지만 모읍니다 (val은 절대 섞지 않음).

    Args:
        target_class_names: 헷갈리는 클래스 이름 목록. classes.txt에 있는 이름과 정확히 일치해야 합니다.

    Returns:
        hard negative train 이미지 폴더 경로.
    """
    class_names = load_class_names()
    target_indices = [class_names.index(n) for n in target_class_names]

    hardneg_images_train = HARDNEG_DIR / "images" / "train"
    hardneg_labels_train = HARDNEG_DIR / "labels" / "train"
    for d in [hardneg_images_train, hardneg_labels_train]:
        d.mkdir(parents=True, exist_ok=True)

    src_labels_dir = LABELS_DIR / "train"
    src_images_dir = IMAGES_DIR / "train"
    count = 0
    for label_path in src_labels_dir.glob("*.txt"):
        with open(label_path, encoding="utf-8") as f:
            lines = f.readlines()
        has_target = any(int(line.split()[0]) in target_indices for line in lines)
        if has_target:
            image_path = src_images_dir / f"{label_path.stem}.png"
            if image_path.exists():
                shutil.copy(image_path, hardneg_images_train / image_path.name)
                shutil.copy(label_path, hardneg_labels_train / label_path.name)
                count += 1
    print(f"train에서 추출된 hard negative 이미지: {count}장")
    return hardneg_images_train


def build_hardneg_yaml(hardneg_images_train: Path) -> Path:
    """hard negative 전용 dataset.yaml을 생성합니다. val은 원본 val 디렉터리를 그대로 참조합니다."""
    original_config = load_config(DATASET_YAML)

    hardneg_yaml = {
        "train": str(hardneg_images_train),
        "val": str(IMAGES_DIR / "val"),
        "names": original_config["names"],
    }

    yaml_path = HARDNEG_DIR / "dataset.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(hardneg_yaml, f, allow_unicode=True)

    print("hard negative용 dataset.yaml 생성 완료")
    print(f"train: {hardneg_yaml['train']}")
    print(f"val:   {hardneg_yaml['val']} (원본 그대로, leakage 없음)")
    return yaml_path


def finetune(base_model_name: str = "yolo26l", epochs: int = 15, lr0: float = 0.0001) -> None:
    """base_model_name의 최신 가중치에서 이어서, hard negative 데이터로 낮은 lr로 fine-tuning합니다.

    메인 학습에서 썼던 scale=0.0 / box=10.0 / dfl=2.0 / CLAHE 강화 설정을 그대로 유지해
    지금까지 고친 부분이 되돌아가지 않게 합니다. 데이터가 적으므로 mosaic도 끕니다.

    Args:
        base_model_name: 이어서 학습할 기존 run 이름 접두사.
        epochs: 추가 학습 epoch 수.
        lr0: 시작 learning rate (기존 학습보다 훨씬 낮게).
    """
    latest_weights = find_latest_run(base_model_name) / "weights" / "best.pt"
    device = get_device()

    hardneg_transforms = [
        A.Rotate(limit=90, border_mode=cv2.BORDER_CONSTANT, crop_border=False, p=0.5),
        A.HorizontalFlip(p=0.5),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.3),
        A.CLAHE(clip_limit=(2.0, 6.0), p=0.3),
    ]

    model = YOLO(latest_weights)
    model.train(
        data=str(HARDNEG_DIR / "dataset.yaml"),
        epochs=epochs,
        lr0=lr0,
        imgsz=640,
        batch=8,
        scale=0.0,
        mosaic=0.0,
        box=10.0,
        dfl=2.0,
        augmentations=hardneg_transforms,
        device=device,
        project=str(OUTPUT_DIR / "runs" / "detect"),
        name=f"{base_model_name}_hardneg",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Hard Negative Mining + Fine-tuning")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="헷갈리는 클래스만 모아 hardneg 데이터셋을 만듭니다.")
    build_parser.add_argument("--classes", nargs="+", required=True, help='예: --classes "리바로정 4mg" "가바토파정 100mg"')

    finetune_parser = sub.add_parser("finetune", help="hardneg 데이터로 추가 fine-tuning을 실행합니다.")
    finetune_parser.add_argument("--base-model-name", default="yolo26l")
    finetune_parser.add_argument("--epochs", type=int, default=15)
    finetune_parser.add_argument("--lr0", type=float, default=0.0001)

    args = parser.parse_args()

    if args.command == "build":
        hardneg_images_train = extract_hard_negative_samples(args.classes)
        build_hardneg_yaml(hardneg_images_train)
    elif args.command == "finetune":
        finetune(base_model_name=args.base_model_name, epochs=args.epochs, lr0=args.lr0)


if __name__ == "__main__":
    main()
