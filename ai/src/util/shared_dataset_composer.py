import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import background_extractor as bg
from tqdm import tqdm

# 설정
IMAGE_ROOT = Path("../../data/raw/train_images")
ANNOT_ROOT = Path("../../data/raw/train_annotations")

OUTPUT = Path("../../data/processed/shared")

TRAIN_RATIO = 0.8
SEED = 42
NUM_BACKGROUNDS = 30
OVERSAMPLE_TARGET_MIN_COUNT = 20

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

class_map = {cid: idx for idx, cid in enumerate(category_ids)}
class_names = [category_dict[cid] for cid in category_ids]

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


def get_combo_id(image_name: str) -> str:
    """파일명 앞부분의 K-코드 조합(콤보 ID)을 추출합니다.

    파일명 패턴: K-XXXXXX-XXXXXX-..._각도_....png → 앞의 K-코드 조합이 콤보 ID입니다.
    같은 콤보는 각도만 다른 같은 물리적 알약 배치이므로, train/val에 걸쳐 나뉘면
    train에서 본 것과 사실상 같은 사진을 val에서 다시 채점하는 데이터 누수가 됩니다.
    """
    return image_name.split("_")[0]


def combo_stratified_split(
    image_meta: dict[str, dict],
    class_map: dict[int, int],
    all_category_ids: list[int],
    train_ratio: float,
    seed: int,
) -> tuple[list[str], list[str]]:
    """콤보(K-코드) 단위로 묶어서 train/val을 분리합니다.

    같은 콤보가 train/val 양쪽에 걸치는 데이터 누수를 원천적으로 방지합니다.
    희귀 클래스의 콤보부터 우선 배정해 클래스 균형을 최대한 맞추고, 마지막에
    train에서 완전히 빠진 클래스가 있으면 val -> train으로 자동 보정합니다.

    Args:
        image_meta: 이미지 파일명 -> {width, height, anns} 메타 정보.
        class_map: 원본 category_id -> YOLO 클래스 인덱스 매핑.
        all_category_ids: 전체 category_id 목록.
        train_ratio: train에 배정할 목표 비율 (0~1).
        seed: 랜덤 시드.

    Returns:
        (train_images, val_images) 이미지 파일명 리스트 튜플.
    """
    rng = random.Random(seed)

    combo_to_images: dict[str, list[str]] = defaultdict(list)
    combo_to_classes: dict[str, set] = defaultdict(set)
    unlabeled_images = []

    for image_name, meta in image_meta.items():
        combo = get_combo_id(image_name)
        combo_to_images[combo].append(image_name)
        classes = {class_map[ann["category_id"]] for ann in meta["anns"]}
        if classes:
            combo_to_classes[combo] |= classes
        else:
            unlabeled_images.append(image_name)

    labeled_combos = [c for c in combo_to_images if combo_to_classes.get(c)]

    all_classes = {class_map[cid] for cid in all_category_ids}

    class_to_combos: dict[int, set] = defaultdict(set)
    for combo, classes in combo_to_classes.items():
        for c in classes:
            class_to_combos[c].add(combo)

    class_order = sorted(class_to_combos.keys(), key=lambda c: len(class_to_combos[c]))

    train_combos = set(labeled_combos)
    val_combos = set()

    for cls_idx in class_order:
        combo_list = list(class_to_combos[cls_idx])
        rng.shuffle(combo_list)

        has_in_val = any(c in val_combos for c in combo_list)
        has_in_train = any(c in train_combos for c in combo_list)

        if not has_in_val and combo_list:
            candidates = [c for c in combo_list if c in train_combos]
            if candidates:
                chosen = candidates[0]
                val_combos.add(chosen)
                train_combos.discard(chosen)

        if not has_in_train and combo_list:
            candidates = [c for c in combo_list if c in val_combos]
            if len(combo_list) > 1 and candidates:
                chosen = candidates[0]
                train_combos.add(chosen)
                val_combos.discard(chosen)

    n_val_target = int(len(labeled_combos) * (1 - train_ratio))
    remaining = [c for c in train_combos if c not in val_combos]
    rng.shuffle(remaining)
    additional_needed = max(0, n_val_target - len(val_combos))
    for combo in remaining[:additional_needed]:
        val_combos.add(combo)
        train_combos.discard(combo)

    # train에 없는 클래스 자동 보정 (val -> train)
    train_class_check = set()
    for combo in train_combos:
        train_class_check |= combo_to_classes[combo]
    missing_in_train = all_classes - train_class_check
    if missing_in_train:
        print(f"\ntrain에 없는 클래스 {len(missing_in_train)}개 자동 보정 중...")
        for cls_idx in missing_in_train:
            combo_list = list(class_to_combos[cls_idx])
            if not combo_list:
                continue
            chosen = combo_list[0]
            if chosen in val_combos:
                val_combos.discard(chosen)
                train_combos.add(chosen)

    train_images = []
    val_images = []
    for combo in train_combos:
        train_images.extend(combo_to_images[combo])
    for combo in val_combos:
        val_images.extend(combo_to_images[combo])

    # 라벨 없는 이미지는 비율대로 랜덤 배정
    rng.shuffle(unlabeled_images)
    cut = round(len(unlabeled_images) * train_ratio)
    train_images.extend(unlabeled_images[:cut])
    val_images.extend(unlabeled_images[cut:])

    rng.shuffle(train_images)
    rng.shuffle(val_images)

    # ===== 검증 로그 =====
    train_class_check = set()
    for combo in train_combos:
        train_class_check |= combo_to_classes[combo]
    val_class_check = set()
    for combo in val_combos:
        val_class_check |= combo_to_classes[combo]
    overlap = train_combos & val_combos

    print(f"\n전체 클래스 수: {len(all_classes)}")
    print(f"train 콤보 {len(train_combos)}개, val 콤보 {len(val_combos)}개")
    print(f"train에 포함된 클래스: {len(train_class_check)} / {len(all_classes)}")
    print(f"val에 포함된 클래스: {len(val_class_check)} / {len(all_classes)}")
    print(f"train/val 콤보 중복(데이터 누수): {len(overlap)}")
    if overlap:
        print(f"⚠️ 여전히 겹치는 콤보가 있습니다: {list(overlap)[:5]}")
    else:
        print("✅ train/val 콤보가 완전히 분리되어 있습니다. 데이터 누수 없음.")

    return train_images, val_images


# train / val split을 콤보(K-코드) 기준 데이터 누수 방지 + 클래스 균형으로 수행
train_images, val_images = combo_stratified_split(
    image_meta, class_map, category_ids, TRAIN_RATIO, SEED
)

# 분할 결과 검증: 각 subset에서 인스턴스가 0개인 클래스가 있는지 확인
for mode, images in (("train", train_images), ("val", val_images)):
    present = Counter()
    for name in images:
        present.update(
            class_map[ann["category_id"]] for ann in image_meta[name]["anns"]
        )
    missing = [
        category_dict[cid] for cid in category_ids if class_map[cid] not in present
    ]
    print(
        f"{mode}: {len(images)} images, {len(present)}/{len(category_ids)} classes present"
        + (f", missing: {missing}" if missing else "")
    )


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

                f.write(f"{cid} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}\n")


def add_background_images(output_dir: Path, num_backgrounds: int, seed: int) -> None:
    """알약이 없는 배경 이미지를 train 전용 negative 샘플로 추가합니다.

    YOLO 는 라벨이 없는(빈 txt) 이미지를 배경으로 학습해 오탐(false positive)을 줄이는 데
    사용합니다. val 로 배경이 새면 학습에 쓰이지 않은 배경 성능을 왜곡해서 측정하게 되므로
    train 에만 추가합니다.

    Args:
        output_dir: shared 데이터셋 루트 디렉토리.
        num_backgrounds: 추가할 배경 이미지 수.
        seed: background_extractor 이미지 샘플링에 사용할 랜덤 seed.
    """
    image_bboxes = bg.collect_image_bboxes(ANNOT_ROOT)
    background_names = bg.select_background_images(image_bboxes, num_backgrounds, seed)

    background_paths = bg.extract_backgrounds(
        background_names, IMAGE_ROOT, image_bboxes, bg.OUTPUT
    )

    for background_path in tqdm(background_paths, desc="Adding backgrounds\t"):
        shutil.copy(background_path, output_dir / "images/train" / background_path.name)

        label_path = output_dir / "labels/train" / f"{background_path.stem}.txt"
        label_path.touch()

    print(f"Added {len(background_paths)} background (empty-label) images to train")


def oversample_rare_classes(
    output_dir: Path, target_min_count: int, class_names: list[str]
) -> None:
    """train에서 target_min_count장 미만으로 등장하는 희귀 클래스를 복제해 채웁니다.

    combo_stratified_split은 콤보(=물리적 알약 배치) 단위로만 train/val을 나눌 뿐
    클래스별 최소 수량까지 보장하지는 않으므로, train 변환이 끝난 뒤 부족한 클래스를
    별도로 채워 학습 시 더 자주 노출되게 합니다.

    Args:
        output_dir: shared 데이터셋 루트 디렉토리.
        target_min_count: 클래스당 train에서 최소로 확보할 이미지 수.
        class_names: 클래스 인덱스 순서로 정렬된 클래스 이름 목록.
    """
    images_dir = output_dir / "images" / "train"
    labels_dir = output_dir / "labels" / "train"

    class_counts: dict[int, int] = {}
    for label_path in labels_dir.glob("*.txt"):
        with open(label_path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                cls_idx = int(line.split()[0])
                class_counts[cls_idx] = class_counts.get(cls_idx, 0) + 1

    low_classes = [
        idx for idx, count in class_counts.items() if count < target_min_count
    ]
    print(f"\noversampling 대상 클래스 {len(low_classes)}개")

    for target_idx in low_classes:
        class_name = class_names[target_idx]
        matched = []
        for label_path in labels_dir.glob("*.txt"):
            with open(label_path, encoding="utf-8") as f:
                has_class = any(
                    line.strip() and int(line.split()[0]) == target_idx for line in f
                )
            if has_class:
                matched.append(label_path.stem)

        current_count = len(matched)
        if current_count == 0:
            continue
        copies_needed = max(0, target_min_count - current_count)
        print(f"{class_name}: 현재 {current_count}개 -> {copies_needed}개 복제")

        for i in range(copies_needed):
            src_stem = matched[i % current_count]
            new_stem = f"{src_stem}_dup{i}"

            shutil.copy(images_dir / f"{src_stem}.png", images_dir / f"{new_stem}.png")
            shutil.copy(labels_dir / f"{src_stem}.txt", labels_dir / f"{new_stem}.txt")

    print("oversampling 완료")


convert(train_images, "train")
convert(val_images, "val")
add_background_images(OUTPUT, NUM_BACKGROUNDS, SEED)
oversample_rare_classes(OUTPUT, OVERSAMPLE_TARGET_MIN_COUNT, class_names)

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
