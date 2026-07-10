"""data/collect 에 내려받은 원본 압축 데이터를 풀어서 class_table.csv 의 category_id 에
해당하는 항목만 걸러낸 뒤 data/raw/train_images, data/raw/train_annotations 로 옮깁니다.

data/collect/images, data/collect/labels 의 tar 파일 안에는 큰 zip 이 여러 조각
(``*.zip.part<byte offset>``)으로 분할되어 들어 있으므로, 압축 해제 시 조각을 offset
순서대로 이어붙인 뒤 압축을 풉니다.
"""

import csv
import json
import re
import shutil
import tarfile
import zipfile
from pathlib import Path

from tqdm import tqdm

COLLECT_ROOT = Path("../../data/collect")
CLASS_TABLE_PATH = COLLECT_ROOT / "class_table.csv"
IMAGES_TAR_DIR = COLLECT_ROOT / "images"
LABELS_TAR_DIR = COLLECT_ROOT / "labels"

WORK_DIR = COLLECT_ROOT / "_extracted"
WORK_IMAGES_DIR = WORK_DIR / "images"
WORK_LABELS_DIR = WORK_DIR / "labels"

RAW_ROOT = Path("../../data/raw")
RAW_IMAGES_DIR = RAW_ROOT / "train_images"
RAW_ANNOTATIONS_DIR = RAW_ROOT / "train_annotations"

ZIP_PART_PATTERN = re.compile(r"^(?P<base>.+\.zip)\.part(?P<offset>\d+)$")


def load_class_table(csv_path: Path) -> dict[int, str]:
    """class_table.csv 를 읽어 category_id -> class_name 매핑을 만듭니다.

    Args:
        csv_path: class_table.csv 파일 경로.

    Returns:
        category_id 를 key, class_name 을 value 로 갖는 딕셔너리.
    """
    class_table = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            class_table[int(row["category_id"])] = row["class_name"]
    return class_table


def extract_archives(tar_dir: Path, target_dir: Path) -> None:
    """tar_dir 안의 모든 tar 파일을 풀어, 분할된 zip 조각을 합친 뒤 target_dir 에 압축 해제합니다.

    Args:
        tar_dir: download_*.tar 파일들이 들어 있는 디렉토리.
        target_dir: 최종적으로 압축을 풀어낼 대상 디렉토리.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    tar_paths = sorted(tar_dir.glob("*.tar"))
    for tar_path in tqdm(tar_paths, desc=f"Extracting tar ({tar_dir.name})\t"):
        tar_extract_dir = target_dir / f"_{tar_path.stem}"
        tar_extract_dir.mkdir(parents=True, exist_ok=True)

        with tarfile.open(tar_path) as tar:
            tar.extractall(tar_extract_dir, filter="data")

        parts_by_zip: dict[str, list[Path]] = {}
        for part_path in tar_extract_dir.rglob("*.zip.part*"):
            match = ZIP_PART_PATTERN.match(part_path.name)
            if match is None:
                continue
            parts_by_zip.setdefault(match.group("base"), []).append(part_path)

        for zip_name, parts in tqdm(
            parts_by_zip.items(), desc=f"Merging & unzipping {tar_path.name}\t", leave=False
        ):
            parts.sort(key=lambda p: int(ZIP_PART_PATTERN.match(p.name).group("offset")))

            merged_zip_path = tar_extract_dir / zip_name
            with open(merged_zip_path, "wb") as merged:
                for part_path in parts:
                    with open(part_path, "rb") as part_f:
                        shutil.copyfileobj(part_f, merged)

            with zipfile.ZipFile(merged_zip_path) as zf:
                zf.extractall(target_dir)

        shutil.rmtree(tar_extract_dir)


def parse_component_category_ids(combo_name: str) -> list[int]:
    """콤보 이름(예: K-000250-000573-002483-006192)에서 개별 category_id 목록을 추출합니다.

    Args:
        combo_name: "K-xxxxxx-...json" 폴더명이나 "K-xxxxxx-..._0_2_0_2_70_000_200.png"
            처럼 K- 로 시작하는 이미지/라벨 이름.

    Returns:
        콤보를 구성하는 category_id(정수) 목록.
    """
    stem = combo_name.split("_")[0]
    codes = stem.split("-")[1:]
    return [int(code) for code in codes]


def remove_invalid_categories(labels_dir: Path, images_dir: Path, valid_category_ids: set[int]) -> None:
    """valid_category_ids 에 속하지 않는 콤보를 labels_dir, images_dir 에서 삭제합니다.

    콤보를 구성하는 category_id 중 하나라도 valid_category_ids 에 없으면 해당 콤보의
    라벨 폴더와 이미지 파일을 통째로 지웁니다.

    Args:
        labels_dir: 압축이 풀린 라벨(json) 루트 디렉토리.
        images_dir: 압축이 풀린 이미지(png) 루트 디렉토리.
        valid_category_ids: class_table.csv 에 정의된 유효 category_id 집합.
    """
    combo_dirs = [p for p in labels_dir.rglob("*_json") if p.is_dir()]
    for combo_dir in tqdm(combo_dirs, desc="Removing invalid categories\t"):
        category_ids = parse_component_category_ids(combo_dir.name)
        if all(cid in valid_category_ids for cid in category_ids):
            continue

        shutil.rmtree(combo_dir)

        combo_base = combo_dir.name[: -len("_json")]
        for image_path in images_dir.rglob(f"{combo_base}_*.png"):
            image_path.unlink()


def _normalize_annotation(json_path: Path, category_id: int, category_name: str) -> None:
    """어노테이션 json 의 category_id/name 을 실제 약물 정보로 바로잡고 raw 데이터와 동일한
    포맷(4-space indent)으로 다시 저장합니다.

    Args:
        json_path: 수정할 어노테이션 json 파일 경로.
        category_id: 이 json 이 속한 폴더가 나타내는 약물의 category_id.
        category_name: category_id 에 대응하는 약물명.
    """
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    for annotation in data["annotations"]:
        annotation["category_id"] = category_id

    for category in data["categories"]:
        category["id"] = category_id
        category["name"] = category_name

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def move_filtered_data(
    labels_dir: Path,
    images_dir: Path,
    raw_annotations_dir: Path,
    raw_images_dir: Path,
    class_table: dict[int, str],
) -> None:
    """필터링된 라벨/이미지를 raw 데이터셋으로 옮기고, 그 과정에서 json 포맷을 raw 데이터와 통일합니다.

    Args:
        labels_dir: 필터링이 끝난 라벨(json) 루트 디렉토리.
        images_dir: 필터링이 끝난 이미지(png) 루트 디렉토리.
        raw_annotations_dir: 라벨을 최종적으로 옮길 data/raw/train_annotations 경로.
        raw_images_dir: 이미지를 최종적으로 옮길 data/raw/train_images 경로.
        class_table: category_id -> class_name 매핑.
    """
    raw_annotations_dir.mkdir(parents=True, exist_ok=True)
    raw_images_dir.mkdir(parents=True, exist_ok=True)

    combo_dirs = [p for p in labels_dir.rglob("*_json") if p.is_dir()]
    for combo_dir in tqdm(combo_dirs, desc="Normalizing & moving annotations\t"):
        for category_dir in [p for p in combo_dir.iterdir() if p.is_dir()]:
            category_id = parse_component_category_ids(category_dir.name)[0]
            category_name = class_table[category_id]

            for json_path in category_dir.glob("*.json"):
                _normalize_annotation(json_path, category_id, category_name)

        destination = raw_annotations_dir / combo_dir.name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(combo_dir), str(destination))

    image_paths = list(images_dir.rglob("*.png"))
    for image_path in tqdm(image_paths, desc="Moving images\t"):
        destination = raw_images_dir / image_path.name
        if destination.exists():
            image_path.unlink()
            continue
        shutil.move(str(image_path), str(destination))


def main() -> None:
    class_table = load_class_table(CLASS_TABLE_PATH)
    valid_category_ids = set(class_table.keys())

    extract_archives(IMAGES_TAR_DIR, WORK_IMAGES_DIR)
    extract_archives(LABELS_TAR_DIR, WORK_LABELS_DIR)

    remove_invalid_categories(WORK_LABELS_DIR, WORK_IMAGES_DIR, valid_category_ids)

    move_filtered_data(WORK_LABELS_DIR, WORK_IMAGES_DIR, RAW_ANNOTATIONS_DIR, RAW_IMAGES_DIR, class_table)

    shutil.rmtree(WORK_DIR, ignore_errors=True)


if __name__ == "__main__":
    main()