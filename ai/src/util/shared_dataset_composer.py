import json
import random
import shutil
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

# train / val split을 이미지 단위로 수행 (Fix 2)
all_images = list(image_meta.keys())
random.shuffle(all_images)

split = int(len(all_images) * TRAIN_RATIO)

train_images = all_images[:split]
val_images = all_images[split:]


def find_image(image_name: str) -> Path | None:
    # Fix 3: 올바른 경로로 직접 탐색
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