import shutil
from pathlib import Path

import albumentations as A
import cv2
import torch
import yaml
from ultralytics import YOLO

YOLO_DIR = Path(__file__).parent

DATASET_PATHS = {
    "v1": "../../data/processed/shared/dataset.yaml",
    "v2": "../../data/processed/shared_v2/dataset.yaml",
}

DATA_DIRS = {
    "v1": "../../data/processed/shared",
    "v2": "../../data/processed/shared_v2",
}

HARDNEG_DIR = YOLO_DIR / "hardneg"


def load_config(config_path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_device() -> int | str:
    if torch.cuda.is_available():
        print("CUDA is available. Using GPU.")
        return 0
    if torch.backends.mps.is_available():
        print("MPS is available. Using MPS.")
        return "mps"
    print("CUDA or MPS is not available. Using CPU.")
    return "cpu"


def load_class_names(dataset_version: str = "v1") -> list:
    """classes.txt에서 클래스 이름 목록을 순서대로 읽어옵니다."""
    classes_file = (YOLO_DIR / DATA_DIRS[dataset_version] / "classes.txt").resolve()
    with open(classes_file, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def extract_hard_negative_samples(
    target_class_names: list, dataset_version: str = "v1"
) -> Path:
    """지정한 클래스가 포함된 train 이미지만 모읍니다 (val은 절대 섞지 않음).

    Args:
        target_class_names: 헷갈리는 클래스 이름 목록. classes.txt에 있는 이름과 정확히 일치해야 합니다.
        dataset_version: 사용할 데이터셋 버전 ("v1" 또는 "v2").

    Returns:
        hard negative train 이미지 폴더 경로.
    """
    class_names = load_class_names(dataset_version)
    target_indices = [class_names.index(n) for n in target_class_names]

    data_dir = (YOLO_DIR / DATA_DIRS[dataset_version]).resolve()
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


def build_hardneg_yaml(hardneg_images_train: Path, dataset_version: str = "v1") -> Path:
    """hard negative 전용 dataset.yaml을 생성합니다. val은 원본 val 디렉터리를 그대로 참조합니다."""
    data_dir = (YOLO_DIR / DATA_DIRS[dataset_version]).resolve()
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


def resolve_trained_weights(model, results, model_name: str) -> Path:
    """방금 끝난 학습의 best.pt 경로를 최대한 안정적으로 찾습니다.

    ultralytics 버전에 따라 학습 결과 객체(results)에 save_dir 속성이 없을 수 있어,
    model.trainer.save_dir -> results.save_dir -> runs 폴더 최신 mtime 스캔 순으로
    시도합니다. 하나에만 의존하지 않기 위한 안전장치입니다.

    Args:
        model: 방금 학습을 마친 YOLO 모델 인스턴스.
        results: model.train()의 반환값.
        model_name: 폴백 스캔 시 사용할 run 이름 접두사.

    Raises:
        FileNotFoundError: 세 가지 방식 모두 best.pt를 찾지 못한 경우.
    """
    candidates = []

    trainer = getattr(model, "trainer", None)
    if trainer is not None and getattr(trainer, "save_dir", None):
        candidates.append(Path(trainer.save_dir))

    if results is not None and getattr(results, "save_dir", None):
        candidates.append(Path(results.save_dir))

    for save_dir in candidates:
        best_pt = save_dir / "weights" / "best.pt"
        if best_pt.exists():
            return best_pt

    # 위 두 방식이 다 실패하면, runs/detect에서 model_name으로 시작하는 가장 최근 run으로 대체
    runs_dir = YOLO_DIR / "runs/detect"
    fallback = sorted(
        [
            d
            for d in runs_dir.glob(f"{model_name}*")
            if (d / "weights/best.pt").exists()
        ],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if fallback:
        return fallback[0] / "weights" / "best.pt"

    raise FileNotFoundError(
        f"방금 끝난 학습의 best.pt를 찾지 못했습니다. {runs_dir} 아래에서 직접 확인해주세요."
    )


def run_hard_negative_finetune(
    base_weights: Path,
    base_model_name: str,
    target_class_names: list,
    dataset_version: str,
    device,
    epochs: int = 15,
    lr0: float = 0.0001,
) -> None:
    """방금 끝난 학습 결과를 대상으로, 가장 헷갈리는 클래스만 모아 추가 fine-tuning합니다.

    학습 파이프라인의 마지막 단계로 main()에서 호출됩니다. val은 절대 건드리지 않아
    confusion matrix 등 이후 평가의 신뢰성을 유지합니다.

    Args:
        base_weights: 방금 끝난 학습의 best.pt 경로.
        base_model_name: 결과 run 이름에 붙일 접두사.
        target_class_names: 헷갈리는 클래스 이름 목록.
        dataset_version: 사용할 데이터셋 버전.
        device: 학습에 사용할 디바이스.
        epochs: 추가 학습 epoch 수.
        lr0: 시작 learning rate (기존 학습보다 훨씬 낮게).
    """
    print(f"\n[Hard Negative Mining] 대상 클래스: {target_class_names}")
    hardneg_images_train = extract_hard_negative_samples(
        target_class_names, dataset_version
    )
    build_hardneg_yaml(hardneg_images_train, dataset_version)

    hardneg_transforms = [
        A.Rotate(limit=90, border_mode=cv2.BORDER_CONSTANT, crop_border=False, p=0.5),
        A.HorizontalFlip(p=0.5),
        A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.3),
        A.CLAHE(clip_limit=(2.0, 6.0), p=0.3),
    ]

    model = YOLO(base_weights)
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
        project=str(YOLO_DIR / "runs/detect"),
        name=f"{base_model_name}_hardneg",
    )


def main(
    model_name: str = "yolo11s",
    dataset_version: str = "v1",
    hardneg_classes: list | None = None,
):
    """모델을 학습합니다. hardneg_classes가 주어지면, 학습 직후 그 클래스들을 대상으로
    Hard Negative Mining + Fine-tuning까지 이어서 실행합니다 (파이프라인의 마지막 단계).

    Args:
        model_name: config/ 폴더에 있는 모델 설정 파일 이름(확장자 제외).
        dataset_version: 사용할 데이터셋 버전 ("v1" 또는 "v2").
        hardneg_classes: Hard Negative Mining 대상 클래스 이름 목록. None이면 생략합니다.
    """
    device = get_device()

    train_config = load_config(YOLO_DIR / "train.yaml")
    model_config = load_config(YOLO_DIR / f"{model_name}.yaml")

    config = {**train_config, **model_config}
    config.pop("augmentations", None)

    model_pt = YOLO_DIR / config.pop("model")
    config["data"] = str((YOLO_DIR / DATASET_PATHS[dataset_version]).resolve())

    custom_transforms = [
        # A.Rotate(limit=180, border_mode=cv2.BORDER_CONSTANT, crop_border=False, p=0.8),
    ]

    model = YOLO(model_pt)
    results = model.train(
        **config,
        augmentations=custom_transforms,
        device=device,
        project=str(YOLO_DIR / "runs/detect"),
    )

    if hardneg_classes:
        best_weights = resolve_trained_weights(model, results, model_name)
        run_hard_negative_finetune(
            base_weights=best_weights,
            base_model_name=model_name,
            target_class_names=hardneg_classes,
            dataset_version=dataset_version,
            device=device,
        )


if __name__ == "__main__":
    main()
