"""가장 헷갈리는 클래스 쌍에 대한 Hard Negative Mining 및 추가 Fine-tuning.

train에서만 대상 클래스가 포함된
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
import torch
import yaml
from ultralytics import YOLO

YOLO_DIR = Path(__file__).parent

DATASET_PATHS = {
    "v1": "../../data/processed/shared",
    "v2": "../../data/processed/shared_v2",
}

HARDNEG_DIR = YOLO_DIR / "hardneg"


def load_config(config_path):
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_device():
    if torch.cuda.is_available():
        print("CUDA is available. Using GPU.")
        return 0
    if torch.backends.mps.is_available():
        print("MPS is available. Using MPS.")
        return "mps"
    print("CUDA or MPS is not available. Using CPU.")
    return "cpu"


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


def load_class_names(dataset_version: str = "v1"):
    """classes.txt에서 클래스 이름 목록을 순서대로 읽어옵니다."""
    classes_file = (YOLO_DIR / DATASET_PATHS[dataset_version] / "classes.txt").resolve()
    with open(classes_file, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def extract_hard_negative_samples(
    target_class_names: list, dataset_version: str = "v1"
):
    """지정한 클래스가 포함된 train 이미지만 모읍니다 (val은 절대 섞지 않음).

    Args:
        target_class_names: 헷갈리는 클래스 이름 목록. classes.txt에 있는 이름과 정확히 일치해야 합니다.
        dataset_version: 사용할 데이터셋 버전 ("v1" 또는 "v2").

    Returns:
        hard negative train 이미지 폴더 경로.
    """
    class_names = load_class_names(dataset_version)
    target_indices = [class_names.index(n) for n in target_class_names]

    data_dir = (YOLO_DIR / DATASET_PATHS[dataset_version]).resolve()
    src_images_dir = data_dir / "images" / "train"
    src_labels_dir = data_dir / "labels" / "train"

    hardneg_images_train = HARDNEG_DIR / "images" / "train"
    hardneg_labels_train = HARDNEG_DIR / "labels" / "train"
    for d in [hardneg_images_train, hardneg_labels_train]:
        d.mkdir(parents=True, exist_ok=True)

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


def build_hardneg_yaml(hardneg_images_train: Path, dataset_version: str = "v1"):
    """hard negative 전용 dataset.yaml을 생성합니다. val은 원본 val 디렉터리를 그대로 참고합니다."""
    data_dir = (YOLO_DIR / DATASET_PATHS[dataset_version]).resolve()
    original_config = load_config(data_dir / "dataset.yaml")

    hardneg_yaml = {
        "train": str(hardneg_images_train),
        "val": str(data_dir / "images" / "val"),
        "names": original_config["names"],
    }

    yaml_path = HARDNEG_DIR / "dataset.yaml"
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(hardneg_yaml, f, allow_unicode=True)

    print("hard negative용 dataset.yaml 생성 완료")
    print(f"train: {hardneg_yaml['train']}")
    print(f"val:   {hardneg_yaml['val']} (원본 그대로, leakage 없음)")
    return yaml_path


def finetune(base_model_name: str = "yolo26l", epochs: int = 15, lr0: float = 0.0001):
    """base_model_name의 최신 가중치에서 이어서, hard negative 데이터로 낮은 lr로 fine-tuning합니다.

    Args:
        base_model_name: 이어서 학습할 기존 run 이름 접두사.
        epochs: 추가 학습 epoch 수.
        lr0: 시작 learning rate.
    """
    best_pt = find_best_weights(base_model_name)
    if best_pt is None:
        print(
            f"[오류] '{base_model_name}'의 학습된 가중치(best.pt)를 찾을 수 없습니다."
        )
        print("먼저 학습(train)을 실행하세요.")
        return

    device = get_device()

    hardneg_transforms = [
        A.Rotate(limit=90, border_mode=cv2.BORDER_CONSTANT, crop_border=False, p=0.5),
        A.HorizontalFlip(p=0.5),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.3),
        A.CLAHE(clip_limit=(2.0, 6.0), p=0.3),
    ]

    model = YOLO(best_pt)
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
        project=str(YOLO_DIR / "runs" / "detect"),
        name=f"{base_model_name}_hardneg",
    )


def main():
    parser = argparse.ArgumentParser(description="Hard Negative Mining + Fine-tuning")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser(
        "build", help="헷갈리는 클래스만 모아 hardneg 데이터셋을 만듭니다."
    )
    build_parser.add_argument(
        "--classes",
        nargs="+",
        required=True,
        help='예: --classes "리바로정 4mg" "가바토파정 100mg"',
    )
    build_parser.add_argument("--dataset-version", default="v1")

    finetune_parser = sub.add_parser(
        "finetune", help="hardneg 데이터로 추가 fine-tuning을 실행합니다."
    )
    finetune_parser.add_argument("--base-model-name", default="yolo26l")
    finetune_parser.add_argument("--epochs", type=int, default=15)
    finetune_parser.add_argument("--lr0", type=float, default=0.0001)

    args = parser.parse_args()

    if args.command == "build":
        hardneg_images_train = extract_hard_negative_samples(
            args.classes, args.dataset_version
        )
        build_hardneg_yaml(hardneg_images_train, args.dataset_version)
    elif args.command == "finetune":
        finetune(base_model_name=args.base_model_name, epochs=args.epochs, lr0=args.lr0)


if __name__ == "__main__":
    main()
