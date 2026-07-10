# ============================================================
# 파일 역할: train.py
# YOLO26l 실제 학습을 실행하는 파일.
# config/train.yaml(공통 하이퍼파라미터) + config/yolo26l.yaml(모델 지정)을
# 합쳐서 학습을 돌림. augmentation(albumentations)도 여기서 정의.
# 실행: python train.py
# ============================================================
"""YOLO26l 학습 스크립트.

사용 예:
    python train.py
    python train.py --model-name yolo26l
"""

import argparse

import albumentations as A
import cv2
from ultralytics import YOLO

from common import DATASET_YAML, OUTPUT_DIR, YOLO_DIR, get_device, load_config


def build_augmentations() -> list:
    """알약 데이터셋에 맞춘 albumentations 증강 세트를 만듭니다.

    회전은 180 -> 90도로 완화(과도한 회전이 bbox를 헐겁게 만드는 부작용 방지),
    CLAHE는 각인 텍스트 대비 강화를 위해 강도를 높였습니다.
    """
    return [
        A.Rotate(limit=90, border_mode=cv2.BORDER_CONSTANT, crop_border=False, p=0.5),
        A.HorizontalFlip(p=0.5),
        A.Affine(translate_percent=0.1, scale=(0.95, 1.05), rotate=0, p=0.3),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.3),
        A.GaussNoise(p=0.2),
        A.ISONoise(p=0.2),
        A.MotionBlur(blur_limit=5, p=0.2),
        A.GaussianBlur(blur_limit=(3, 7), p=0.2),
        A.CLAHE(clip_limit=(2.0, 6.0), p=0.3),
        A.RandomShadow(p=0.2),
        A.CoarseDropout(p=0.2),
        A.ImageCompression(quality_range=(60, 100), p=0.2),
    ]


def main(model_name: str = "yolo26l") -> None:
    """train.yaml + {model_name}.yaml 설정을 합쳐 학습을 실행합니다.

    Args:
        model_name: config/ 폴더에 있는 모델 설정 파일 이름(확장자 제외).
    """
    device = get_device()

    train_config = load_config(YOLO_DIR / "config" / "train.yaml")
    model_config = load_config(YOLO_DIR / "config" / f"{model_name}.yaml")

    config = {**train_config, **model_config}
    config.pop("augmentations", None)

    model_pt = YOLO_DIR / config.pop("model")
    config["data"] = str(DATASET_YAML)

    model = YOLO(model_pt)
    model.train(
        **config,
        augmentations=build_augmentations(),
        device=device,
        project=str(OUTPUT_DIR / "runs" / "detect"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO26l 학습")
    parser.add_argument("--model-name", default="yolo26l", help="config/{model_name}.yaml을 사용합니다.")
    args = parser.parse_args()
    main(model_name=args.model_name)
