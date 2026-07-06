import json
import random
import shutil
from collections import Counter
from pathlib import Path
from tqdm import tqdm

# 설정
IMAGE_ROOT = Path("../../data/raw/train_images")
ANNOT_ROOT = Path("../../data/raw/train_annotations")

OUTPUT = Path("../../data/processed/shared")

TRAIN_RATIO = 0.8
SEED = 42

random.seed(SEED)

# 출력 폴더 생성
for p in [
    OUTPUT / "images/train",
    OUTPUT / "images/val",
    OUTPUT / "labels/train",
    OUTPUT / "labels/val",
]:
    p.mkdir(parents=True, exist_ok=True)

# 모든 JSON 검색
json_files = sorted(ANNOT_ROOT.rglob("*.json"))

print(f"Found {len(json_files)} json files")

# category 수집
category_dict = {}

for jf in tqdm(json_files, desc="Collecting categories\t"):

    with open(jf, encoding="utf-8") as f:
        data = json.load(f)

    for cat in data["categories"]:
        category_dict[cat["id"]] = cat["name"]

category_ids = sorted(category_dict.keys())

class_map = {
    cid: idx
    for idx, cid in enumerate(category_ids)
}

# 저장
with open(OUTPUT / "class_mapping.json", "w", encoding="utf-8") as f:
    json.dump(class_map, f, indent=4, ensure_ascii=False)

with open(OUTPUT / "classes.txt", "w", encoding="utf-8") as f:
    for cid in category_ids:
        f.write(category_dict[cid] + "\n")

print(f"{len(category_ids)} classes")

# image_name → {width, height, anns}
image_meta: dict[str, dict] = {}

for jf in tqdm(json_files, desc="Parsing annotations\t"):

    with open(jf, encoding="utf-8") as f:
        data = json.load(f)

    image = data["images"][0]
    image_name = image["file_name"]

    if image_name not in image_meta:
        image_meta[image_name] = {
            "width": image["width"],
            "height": image["height"],
            "anns": [],
        }

    for ann in data["annotations"]:
        image_meta[image_name]["anns"].append(ann)

print(f"Total unique images: {len(image_meta)}")

def stratified_split(
    image_meta: dict[str, dict],
    class_map: dict[int, int],
    train_ratio: float,
    seed: int,
) -> tuple[list[str], list[str]]:
    """
    클래스별 인스턴스 수가 train/val에 train_ratio 비율대로 고르게 배분되도록 층화 분할합니다.

    Args:
        image_meta: 이미지 파일명 → {width, height, anns} 메타 정보
        class_map: 원본 category_id → YOLO 클래스 인덱스 매핑
        train_ratio: train에 배정할 비율 (0~1)
        seed: 랜덤 seed

    Returns:
        (train_images, val_images) 이미지 파일명 리스트 튜플
    """
    rng = random.Random(seed)

    image_class_counts: dict[str, Counter] = {}
    class_total: Counter = Counter()

    for image_name, meta in image_meta.items():
        counts = Counter(class_map[ann["category_id"]] for ann in meta["anns"])
        image_class_counts[image_name] = counts
        class_total.update(counts)

    ratios = {"train": train_ratio, "val": 1 - train_ratio}
    desired = {
        subset: {cid: cnt * r for cid, cnt in class_total.items()}
        for subset, r in ratios.items()
    }

    remaining = {
        name: counts for name, counts in image_class_counts.items() if counts
    }
    unlabeled_images = [
        name for name, counts in image_class_counts.items() if not counts
    ]
    assigned: dict[str, list[str]] = {"train": [], "val": []}

    while remaining:
        # 아직 미배정 이미지가 남아 있는 클래스 중 가장 희귀한 클래스 선택
        class_remaining_images: Counter = Counter()
        for counts in remaining.values():
            class_remaining_images.update(counts.keys())

        rarest_cid = min(
            class_remaining_images,
            key=lambda cid: (class_remaining_images[cid], cid),
        )

        candidates = [name for name, counts in remaining.items() if rarest_cid in counts]
        rng.shuffle(candidates)

        for name in candidates:
            counts = remaining.pop(name)

            # 해당 클래스가 더 부족한(desired가 큰) subset에 배정,
            # 동률이면 전체 desired 합이 더 큰 subset, 그래도 동률이면 랜덤
            def subset_key(subset: str) -> tuple[float, float, float]:
                return (
                    desired[subset].get(rarest_cid, 0.0),
                    sum(desired[subset].values()),
                    rng.random(),
                )

            subset = max(("train", "val"), key=subset_key)

            assigned[subset].append(name)
            for cid, cnt in counts.items():
                desired[subset][cid] = desired[subset].get(cid, 0.0) - cnt

    # 라벨이 없는 이미지는 비율대로 랜덤 배정
    rng.shuffle(unlabeled_images)
    cut = round(len(unlabeled_images) * train_ratio)
    assigned["train"].extend(unlabeled_images[:cut])
    assigned["val"].extend(unlabeled_images[cut:])

    rng.shuffle(assigned["train"])
    rng.shuffle(assigned["val"])

    return assigned["train"], assigned["val"]


# train / val split을 클래스 층화 기준으로 수행
train_images, val_images = stratified_split(image_meta, class_map, TRAIN_RATIO, SEED)

# 분할 결과 검증: 각 subset에서 인스턴스가 0개인 클래스가 있는지 확인
for mode, images in (("train", train_images), ("val", val_images)):
    present = Counter()
    for name in images:
        present.update(
            class_map[ann["category_id"]] for ann in image_meta[name]["anns"]
        )
    missing = [category_dict[cid] for cid in category_ids if class_map[cid] not in present]
    print(f"{mode}: {len(images)} images, {len(present)}/{len(category_ids)} classes present"
          + (f", missing: {missing}" if missing else ""))


def find_image(image_name: str) -> Path | None:
    candidate = IMAGE_ROOT / image_name
    if candidate.exists():
        return candidate

    # 직접 경로에 없으면 전체 검색
    result = list(IMAGE_ROOT.rglob(image_name))
    return result[0] if result else None


def convert(image_names: list[str], mode: str):
    """이미지별 통합 어노테이션을 YOLO 데이터셋 형식으로 변환합니다.

    Args:
        image_names: 변환할 이미지 파일명 목록
        mode: 데이터셋 분할 이름. "train" 또는 "val"을 사용합니다.
    """
    for image_name in tqdm(image_names, desc=f"Converting {mode}\t"):

        meta = image_meta[image_name]
        width = meta["width"]
        height = meta["height"]

        img_path = find_image(image_name)

        if img_path is None:
            print("Image not found:", image_name)
            continue

        shutil.copy(img_path, OUTPUT / f"images/{mode}" / image_name)

        txt_path = OUTPUT / f"labels/{mode}" / f"{Path(image_name).stem}.txt"

        with open(txt_path, "w") as f:

            for ann in meta["anns"]:

                cid = class_map[ann["category_id"]]

                x, y, w, h = ann["bbox"]

                xc = (x + w / 2) / width
                yc = (y + h / 2) / height
                wn = w / width
                hn = h / height

                f.write(
                    f"{cid} "
                    f"{xc:.6f} "
                    f"{yc:.6f} "
                    f"{wn:.6f} "
                    f"{hn:.6f}\n"
                )


convert(train_images, "train")
convert(val_images, "val")

# dataset.yaml
with open(OUTPUT / "dataset.yaml", "w", encoding="utf-8") as f:

    f.write(f"path: {OUTPUT.resolve()}\n")
    f.write("train: images/train\n")
    f.write("val: images/val\n\n")

    f.write("names:\n")

    for cid in category_ids:
        idx = class_map[cid]
        f.write(f"  {idx}: {category_dict[cid]}\n")

print("Done!")