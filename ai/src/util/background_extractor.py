"""data/raw/train_images 에서 일부 이미지를 뽑아, train_annotations 의 bbox 로 알약 영역을
마스킹한 뒤 cv2.inpaint 로 채워 넣어 알약이 없는 배경 이미지를 만듭니다.

만들어진 배경 이미지는 data/processed/backgrounds 에 저장되며, 추후
shared_dataset_composer.py 에서 합성 데이터 생성용 배경으로 사용할 예정입니다.
"""

import json
import random
from pathlib import Path

import cv2
import numpy as np
from tqdm import tqdm

IMAGE_ROOT = Path("../../data/raw/train_images")
ANNOT_ROOT = Path("../../data/raw/train_annotations")

OUTPUT = Path("../../data/processed/backgrounds")

NUM_BACKGROUNDS = 30
MASK_PADDING = 10  # bbox 주변 여유 픽셀 (알약 그림자/경계 잔상 제거용)
INPAINT_RADIUS = 5
SEED = 42


def collect_image_bboxes(annot_root: Path) -> dict[str, list[list[float]]]:
    """train_annotations 의 모든 json 을 읽어 image_name -> bbox 목록 매핑을 만듭니다.

    합성 촬영 이미지 한 장에 찍힌 여러 알약의 bbox 가 category 별 폴더의 json 에
    나뉘어 저장되어 있으므로, 같은 image_name 을 참조하는 모든 json 의 bbox 를 모아야
    이미지 안의 알약 영역 전체를 알 수 있습니다.

    Args:
        annot_root: train_annotations 루트 디렉토리.

    Returns:
        image_name(str) -> [[x, y, w, h], ...] bbox 목록 매핑.
    """
    image_bboxes: dict[str, list[list[float]]] = {}

    json_files = sorted(annot_root.rglob("*.json"))
    for jf in tqdm(json_files, desc="Collecting bboxes\t"):
        with open(jf, encoding="utf-8") as f:
            data = json.load(f)

        image_name = data["images"][0]["file_name"]
        bboxes = image_bboxes.setdefault(image_name, [])
        bboxes.extend(ann["bbox"] for ann in data["annotations"])

    return image_bboxes


def build_mask(shape: tuple[int, int], bboxes: list[list[float]], padding: int) -> np.ndarray:
    """bbox 영역(padding 만큼 확장)을 255 로 채운 inpaint 마스크를 만듭니다.

    Args:
        shape: (height, width) 튜플.
        bboxes: [x, y, w, h] 형태의 bbox 목록.
        padding: bbox 를 확장할 여유 픽셀 수.

    Returns:
        shape 크기의 uint8 마스크 (알약 영역 255, 나머지 0).
    """
    height, width = shape
    mask = np.zeros((height, width), dtype=np.uint8)

    for x, y, w, h in bboxes:
        x1 = max(int(x) - padding, 0)
        y1 = max(int(y) - padding, 0)
        x2 = min(int(x + w) + padding, width)
        y2 = min(int(y + h) + padding, height)
        mask[y1:y2, x1:x2] = 255

    return mask


def select_background_images(
    image_bboxes: dict[str, list[list[float]]],
    num_backgrounds: int,
    seed: int,
) -> list[str]:
    """배경으로 만들 이미지 파일명을 무작위로 뽑습니다.

    Args:
        image_bboxes: collect_image_bboxes 로 만든 image_name -> bbox 매핑.
        num_backgrounds: 뽑을 이미지 수.
        seed: 랜덤 seed.

    Returns:
        bbox 가 있는(=알약이 촬영된) 이미지 중 무작위로 뽑은 파일명 목록.
    """
    candidates = sorted(name for name, bboxes in image_bboxes.items() if bboxes)
    sample_size = min(num_backgrounds, len(candidates))

    rng = random.Random(seed)
    return rng.sample(candidates, sample_size)


def extract_backgrounds(
    image_names: list[str],
    image_root: Path,
    image_bboxes: dict[str, list[list[float]]],
    output_dir: Path,
) -> list[Path]:
    """이미지에서 알약 영역을 cv2.inpaint 로 지워 배경 이미지를 만들고 저장합니다.

    Args:
        image_names: 배경으로 만들 이미지 파일명 목록.
        image_root: 원본 이미지가 있는 train_images 디렉토리.
        image_bboxes: collect_image_bboxes 로 만든 image_name -> bbox 매핑.
        output_dir: 배경 이미지를 저장할 디렉토리.

    Returns:
        저장된 배경 이미지 경로 목록 (원본을 찾지 못한 이미지는 제외).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    written_paths: list[Path] = []

    for idx, image_name in enumerate(tqdm(image_names, desc="Inpainting backgrounds\t"), start=1):
        img_path = image_root / image_name
        image = cv2.imread(str(img_path))

        if image is None:
            print("Image not found:", image_name)
            continue

        mask = build_mask(image.shape[:2], image_bboxes[image_name], MASK_PADDING)
        background = cv2.inpaint(image, mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)

        output_path = output_dir / f"background_{idx:02d}.png"
        cv2.imwrite(str(output_path), background)
        written_paths.append(output_path)

    return written_paths


def main() -> None:
    image_bboxes = collect_image_bboxes(ANNOT_ROOT)
    image_names = select_background_images(image_bboxes, NUM_BACKGROUNDS, SEED)

    print(f"Selected {len(image_names)} images out of "
          f"{sum(1 for boxes in image_bboxes.values() if boxes)} candidates")

    extract_backgrounds(image_names, IMAGE_ROOT, image_bboxes, OUTPUT)

    print("Done!")


if __name__ == "__main__":
    main()