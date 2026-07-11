"""data/raw_v2 에 내려받은 조합 알약(경구약제조합) 원본 압축 데이터를 풀어서
train_annotations, train_images 폴더로 정리하고, class_mapping.csv 와 클래스별 라벨 개수
md 파일을 만듭니다.

data/raw_v2 에는 download_TL_*.tar(라벨링데이터), download_TS_*.tar(원천데이터/이미지)가
번호별로 내려받아져 있습니다. tar 안에는 zip 이 분할 조각(``*.zip.part<byte offset>``)으로
들어 있어, offset 순서대로 이어붙인 뒤 압축을 풉니다.

- TL zip 을 풀면 나오는 ``K-<콤보코드>_json/K-<개별코드>/*.json`` 폴더를 그대로
  train_annotations 로 옮깁니다. (한 콤보 이미지 안에 있는 알약마다 별도 json 폴더)
- TS zip 을 풀면 나오는 ``*.png`` 파일은 폴더 구조와 상관없이 파일명 그대로
  train_images 에 평탄하게 모읍니다.

tar 여러 개(TS 는 개당 수 GB)를 순서대로 풀다 보면 중간에 중단될 수 있어, tar 하나를
처리할 때마다 data/raw_v2/_state.json 에 체크포인트를 남깁니다. 다시 실행하면 이미 완료된
TL/TS 번호는 건너뜁니다.

압축 해제 중간 작업 공간(WORK_DIR)은 원본 데이터가 있는 드라이브가 아닌 시스템 임시 폴더를
사용합니다.

train_annotations 추출이 끝나면 모든 json 을 읽어 category_id 별 dl_name/item_seq/라벨
개수를 모아 class_mapping.csv, class_file_counts.md 를 data/raw_v2 에 만듭니다.

이어서 src/util/shared_dataset_composer.py(v1) 와 동일한 방식으로 train/val 을 클래스
층화 분할하고, 배경(negative) 이미지를 더해 YOLO 데이터셋(images/labels + dataset.yaml)을
data/processed/shared_v2 에 만듭니다.
"""

import csv
import json
import random
import re
import shutil
import sys
import tarfile
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

from tqdm import tqdm

# background_extractor.py 는 한 단계 위(util/) 디렉토리에 있어 기본 sys.path 에 없습니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import background_extractor as bg

# Windows 콘솔 기본 코드페이지(cp949)로 인코딩 불가한 문자(예: mojibake 폴더명)가
# 있어도 죽지 않도록 표준출력을 UTF-8로 강제합니다.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAW_V2_ROOT = Path("../../../data/raw_v2")
TRAIN_ANNOT_DIR = RAW_V2_ROOT / "train_annotations"
TRAIN_IMAGES_DIR = RAW_V2_ROOT / "train_images"

CLASS_MAPPING_PATH = RAW_V2_ROOT / "class_mapping.csv"
CLASS_COUNT_MD_PATH = RAW_V2_ROOT / "class_file_counts.md"
STATE_PATH = RAW_V2_ROOT / "_state.json"

WORK_DIR = Path(tempfile.gettempdir()) / "raw_v2_extract"

YOLO_OUTPUT = RAW_V2_ROOT.parent / "processed/shared_v2"
BACKGROUNDS_DIR = RAW_V2_ROOT.parent / "processed/backgrounds_v2"

TRAIN_RATIO = 0.8
SEED = 42
NUM_BACKGROUNDS = 30

random.seed(SEED)

ZIP_PART_PATTERN = re.compile(r"^(?P<base>.+\.zip)\.part(?P<offset>\d+)$")
TL_TAR_PATTERN = re.compile(r"^download_TL_(?P<index>\d+)\.tar$")
TS_TAR_PATTERN = re.compile(r"^download_TS_(?P<index>\d+)\.tar$")


def extract_tar_zip(tar_path: Path, work_dir: Path) -> Path:
    """tar 하나를 풀어, 그 안의 분할 zip 조각을 offset 순서로 이어붙인 뒤 통째로 압축을 풉니다.

    Args:
        tar_path: download_TL_*.tar 또는 download_TS_*.tar 파일 경로.
        work_dir: 작업용 임시 디렉토리.

    Returns:
        zip 을 풀어낸 디렉토리 경로.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = work_dir / f"_{tar_path.stem}_raw"
    shutil.rmtree(raw_dir, ignore_errors=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path) as tar:
        tar.extractall(raw_dir, filter="data")

    extract_dir = work_dir / tar_path.stem
    shutil.rmtree(extract_dir, ignore_errors=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    parts_by_zip: dict[str, list[Path]] = defaultdict(list)
    for part_path in raw_dir.rglob("*.zip.part*"):
        match = ZIP_PART_PATTERN.match(part_path.name)
        if match is None:
            continue
        parts_by_zip[match.group("base")].append(part_path)

    for zip_name, parts in parts_by_zip.items():
        parts.sort(key=lambda p: int(ZIP_PART_PATTERN.match(p.name).group("offset")))

        merged_zip_path = raw_dir / zip_name
        with open(merged_zip_path, "wb") as merged:
            for part_path in parts:
                with open(part_path, "rb") as part_f:
                    shutil.copyfileobj(part_f, merged)

        with zipfile.ZipFile(merged_zip_path) as zf:
            zf.extractall(extract_dir)

    # macOS 에서 압축했을 때 딸려 들어오는 AppleDouble 메타데이터(._*, .DS_Store)는
    # 실제 데이터가 아니라 바이너리라 이후 json/png 처리 중 디코딩 에러를 일으키므로 제거합니다.
    for junk_path in extract_dir.rglob("._*"):
        junk_path.unlink()
    for junk_path in extract_dir.rglob(".DS_Store"):
        junk_path.unlink()

    shutil.rmtree(raw_dir)
    return extract_dir


def process_tl_tar(tar_path: Path, train_annot_dir: Path) -> int:
    """TL tar 를 풀어 콤보별 라벨 폴더를 train_annot_dir 로 옮깁니다.

    Args:
        tar_path: download_TL_*.tar 파일 경로.
        train_annot_dir: 라벨 폴더를 모아둘 대상 디렉토리.

    Returns:
        옮긴 콤보 라벨 폴더 수.
    """
    extract_dir = extract_tar_zip(tar_path, WORK_DIR)

    combo_dirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    for combo_dir in combo_dirs:
        destination = train_annot_dir / combo_dir.name
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(combo_dir), str(destination))

    shutil.rmtree(extract_dir)
    return len(combo_dirs)


def process_ts_tar(tar_path: Path, train_images_dir: Path) -> int:
    """TS tar 를 풀어 이미지 파일을 폴더 구조 없이 train_images_dir 에 평탄하게 모읍니다.

    Args:
        tar_path: download_TS_*.tar 파일 경로.
        train_images_dir: 이미지를 모아둘 대상 디렉토리.

    Returns:
        옮긴 이미지 파일 수.
    """
    extract_dir = extract_tar_zip(tar_path, WORK_DIR)

    png_paths = list(extract_dir.rglob("*.png"))
    for png_path in png_paths:
        shutil.move(str(png_path), str(train_images_dir / png_path.name))

    shutil.rmtree(extract_dir)
    return len(png_paths)


def _process_with_retry(func, tar_path: Path, dest_dir: Path, max_attempts: int = 3) -> int:
    """process_tl_tar/process_ts_tar 를 실행하되, 일시적인 I/O 오류가 나면 재시도합니다.

    Args:
        func: process_tl_tar 또는 process_ts_tar.
        tar_path: 처리할 tar 파일 경로.
        dest_dir: 결과를 옮길 대상 디렉토리.
        max_attempts: 최대 재시도 횟수.

    Returns:
        func 의 반환값(처리된 항목 수).
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return func(tar_path, dest_dir)
        except (zipfile.BadZipFile, EOFError, OSError, tarfile.ReadError):
            if attempt == max_attempts:
                raise
            print(f"[{tar_path.name}] 처리 중 오류 발생, 재시도 ({attempt}/{max_attempts})")

    raise AssertionError("unreachable")


def load_state(path: Path) -> dict:
    """이전 실행에서 남긴 체크포인트를 읽어옵니다. 없으면 빈 상태를 반환합니다.

    Args:
        path: _state.json 경로.

    Returns:
        completed_tl_indices/completed_ts_indices 를 담은 상태 딕셔너리.
    """
    if not path.exists():
        return {"completed_tl_indices": set(), "completed_ts_indices": set()}

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    return {
        "completed_tl_indices": set(raw.get("completed_tl_indices", [])),
        "completed_ts_indices": set(raw.get("completed_ts_indices", [])),
    }


def save_state(state: dict, path: Path) -> None:
    """진행 상황을 _state.json 에 체크포인트로 저장합니다.

    Args:
        state: completed_tl_indices/completed_ts_indices 를 담은 상태 딕셔너리.
        path: _state.json 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        "completed_tl_indices": sorted(state["completed_tl_indices"]),
        "completed_ts_indices": sorted(state["completed_ts_indices"]),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def build_class_mapping(
    train_annot_dir: Path,
) -> tuple[dict[int, dict], Counter, list[dict]]:
    """train_annot_dir 아래 모든 json 을 읽어 category_id 별 정보와 라벨 개수를 모읍니다.

    각 json 은 콤보 이미지 안 알약 하나에 대한 어노테이션입니다. json 의 categories[0]["id"]
    는 실제 알약을 구분하지 못하는 값이라, images[0]["dl_mapping_code"] (예: "K-000250")
    에서 "K-" 를 뗀 숫자를 category_id 로 사용합니다.

    일부 원본 라벨은 bbox 계산에 실패해 "bbox": [] 로 export 되어 있어(전체의 약 0.4%),
    YOLO 라벨로 쓸 수 없으므로 category_counts 에서 제외하고 invalid_bbox_files 에 따로
    모읍니다.

    Args:
        train_annot_dir: train_annotations 디렉토리.

    Returns:
        (category_info, category_counts, invalid_bbox_files) 튜플.
        category_info: category_id -> {dl_name, item_seq}.
        category_counts: category_id -> 유효한 bbox 를 가진 라벨(annotation) 개수.
        invalid_bbox_files: bbox 가 비어있는 annotation 이 있던 json 목록. 각 원소는
            {"path", "category_id", "dl_name"} 딕셔너리입니다.
    """
    json_files = sorted(
        p for p in train_annot_dir.rglob("*.json") if not p.name.startswith("._")
    )

    category_info: dict[int, dict] = {}
    category_counts: Counter = Counter()
    invalid_bbox_files: list[dict] = []

    skipped: list[Path] = []
    for jf in tqdm(json_files, desc="Scanning annotations\t"):
        with open(jf, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[WARN] 손상된 json, 건너뜀: {jf} ({e})")
                skipped.append(jf)
                continue

        image = data["images"][0]
        # categories[0]["id"] 는 거의 항상 1(드물게 다른 임의값)로 고정돼 있어 실제
        # 알약을 구분하지 못합니다. 실제 알약 식별자는 images[0]["dl_mapping_code"]
        # (예: "K-000250") 이므로 "K-" 접두어를 뗀 숫자를 category_id 로 사용합니다.
        cid = int(image["dl_mapping_code"].removeprefix("K-"))
        dl_name = image.get("dl_name")

        for ann in data["annotations"]:
            if len(ann["bbox"]) != 4:
                invalid_bbox_files.append({
                    "path": jf.relative_to(train_annot_dir).as_posix(),
                    "category_id": cid,
                    "dl_name": dl_name,
                })
                continue
            category_counts[cid] += 1

        if cid not in category_info:
            category_info[cid] = {
                "dl_name": dl_name,
                "item_seq": image.get("item_seq"),
            }

    if skipped:
        print(f"[WARN] 총 {len(skipped)}개 json 을 건너뛰었습니다.")
    if invalid_bbox_files:
        print(f"[WARN] bbox 가 비어있는 annotation {len(invalid_bbox_files)}개를 건너뛰었습니다.")

    return category_info, category_counts, invalid_bbox_files


def write_class_mapping_csv(category_info: dict[int, dict], path: Path) -> None:
    """category_id 오름차순으로 class_index 를 매겨 class_mapping.csv 를 저장합니다.

    Args:
        category_info: category_id -> {dl_name, item_seq}.
        path: 저장할 csv 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["class_index", "dl_name", "category_id", "item_seq"])
        for idx, cid in enumerate(sorted(category_info)):
            info = category_info[cid]
            writer.writerow([idx, info["dl_name"], cid, info["item_seq"]])


def write_class_count_md(
    category_info: dict[int, dict],
    category_counts: Counter,
    invalid_bbox_files: list[dict],
    path: Path,
) -> None:
    """클래스별 라벨(annotation) 개수를 markdown 표로 정리합니다.

    Args:
        category_info: category_id -> {dl_name, item_seq}.
        category_counts: category_id -> 라벨 개수.
        invalid_bbox_files: build_class_mapping 이 모은, bbox 가 비어있어 제외된 json 목록.
        path: 저장할 md 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    category_ids = sorted(category_info)
    lines = [
        "# raw_v2 클래스별 라벨 개수",
        "",
        f"- 전체 클래스 수: {len(category_ids)}",
        f"- 전체 라벨(annotation) 수: {sum(category_counts.values())}",
        "",
        "| class_index | category_id | dl_name | item_seq | count |",
        "|---|---|---|---|---|",
    ]
    for idx, cid in enumerate(category_ids):
        info = category_info[cid]
        count = category_counts.get(cid, 0)
        lines.append(f"| {idx} | {cid} | {info['dl_name']} | {info['item_seq']} | {count} |")

    if invalid_bbox_files:
        lines += [
            "",
            f"## bbox 가 비어있어 제외된 파일 ({len(invalid_bbox_files)}개)",
            "",
            "| category_id | dl_name | file |",
            "|---|---|---|",
        ]
        for item in sorted(
            invalid_bbox_files, key=lambda x: (x["category_id"], x["path"])
        ):
            lines.append(
                f"| {item['category_id']} | {item['dl_name']} | {item['path']} |"
            )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_image_annotations(train_annot_dir: Path) -> dict[str, dict]:
    """train_annot_dir 아래 모든 json 을 읽어 image_name 별 크기/annotation 목록을 모읍니다.

    콤보 이미지 한 장 안의 알약마다 별도 json 파일로 나뉘어 있으므로, 같은 file_name 을
    가리키는 annotation 을 모두 모아야 이미지 하나의 라벨이 완성됩니다. category_id 는
    build_class_mapping 과 동일하게 images[0]["dl_mapping_code"] 기준으로 계산합니다.

    Args:
        train_annot_dir: train_annotations 디렉토리.

    Returns:
        image_name -> {"width", "height", "anns"} 매핑.
        anns 의 각 원소는 {"category_id", "bbox"} 딕셔너리입니다.
    """
    json_files = sorted(
        p for p in train_annot_dir.rglob("*.json") if not p.name.startswith("._")
    )

    image_meta: dict[str, dict] = {}
    skipped_anns = 0

    for jf in tqdm(json_files, desc="Parsing annotations\t"):
        with open(jf, encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                continue

        image = data["images"][0]
        cid = int(image["dl_mapping_code"].removeprefix("K-"))
        image_name = image["file_name"]

        meta = image_meta.setdefault(
            image_name,
            {"width": image["width"], "height": image["height"], "anns": []},
        )
        for ann in data["annotations"]:
            # 일부 원본 라벨이 bbox 계산에 실패해 "bbox": [] 로 export 된 경우가 있어
            # (전체의 약 0.4%), YOLO 라벨로 변환할 수 없으므로 건너뜁니다.
            if len(ann["bbox"]) != 4:
                skipped_anns += 1
                continue
            meta["anns"].append({"category_id": cid, "bbox": ann["bbox"]})

    if skipped_anns:
        print(f"[WARN] bbox 가 비어있는 annotation {skipped_anns}개를 건너뛰었습니다.")

    return image_meta


def stratified_split(
    image_meta: dict[str, dict],
    class_map: dict[int, int],
    train_ratio: float,
    seed: int,
) -> tuple[list[str], list[str]]:
    """클래스별 인스턴스 수가 train/val 에 train_ratio 비율대로 고르게 배분되도록 층화 분할합니다.

    Args:
        image_meta: collect_image_annotations 로 만든 이미지 메타 정보.
        class_map: 원본 category_id -> YOLO 클래스 인덱스 매핑.
        train_ratio: train 에 배정할 비율 (0~1).
        seed: 랜덤 seed.

    Returns:
        (train_images, val_images) 이미지 파일명 리스트 튜플.
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


def convert_to_yolo(
    image_meta: dict[str, dict],
    class_map: dict[int, int],
    image_names: list[str],
    mode: str,
    image_root: Path,
    output_dir: Path,
) -> None:
    """이미지별 annotation 을 YOLO 데이터셋 형식(images/labels)으로 변환합니다.

    Args:
        image_meta: collect_image_annotations 로 만든 이미지 메타 정보.
        class_map: 원본 category_id -> YOLO 클래스 인덱스 매핑.
        image_names: 변환할 이미지 파일명 목록.
        mode: 데이터셋 분할 이름. "train" 또는 "val".
        image_root: 원본 이미지가 있는 train_images 디렉토리.
        output_dir: shared_v2 데이터셋 루트 디렉토리.
    """
    for image_name in tqdm(image_names, desc=f"Converting {mode}\t"):
        meta = image_meta[image_name]
        width = meta["width"]
        height = meta["height"]

        img_path = image_root / image_name
        if not img_path.exists():
            print("Image not found:", image_name)
            continue

        shutil.copy(img_path, output_dir / f"images/{mode}" / image_name)

        txt_path = output_dir / f"labels/{mode}" / f"{Path(image_name).stem}.txt"
        with open(txt_path, "w") as f:
            for ann in meta["anns"]:
                cid = class_map[ann["category_id"]]
                x, y, w, h = ann["bbox"]

                xc = (x + w / 2) / width
                yc = (y + h / 2) / height
                wn = w / width
                hn = h / height

                f.write(f"{cid} {xc:.6f} {yc:.6f} {wn:.6f} {hn:.6f}\n")


def add_background_images(
    image_meta: dict[str, dict],
    image_root: Path,
    output_dir: Path,
    backgrounds_dir: Path,
    num_backgrounds: int,
    seed: int,
) -> None:
    """알약이 없는 배경 이미지를 train 전용 negative 샘플로 추가합니다.

    Args:
        image_meta: collect_image_annotations 로 만든 이미지 메타 정보.
        image_root: 원본 이미지가 있는 train_images 디렉토리.
        output_dir: shared_v2 데이터셋 루트 디렉토리.
        backgrounds_dir: inpaint 로 만든 배경 이미지를 저장할 중간 디렉토리.
        num_backgrounds: 추가할 배경 이미지 수.
        seed: 이미지 샘플링에 사용할 랜덤 seed.
    """
    image_bboxes = {
        name: [ann["bbox"] for ann in meta["anns"]] for name, meta in image_meta.items()
    }
    background_names = bg.select_background_images(image_bboxes, num_backgrounds, seed)
    background_paths = bg.extract_backgrounds(background_names, image_root, image_bboxes, backgrounds_dir)

    for background_path in tqdm(background_paths, desc="Adding backgrounds\t"):
        shutil.copy(background_path, output_dir / "images/train" / background_path.name)

        label_path = output_dir / "labels/train" / f"{background_path.stem}.txt"
        label_path.touch()

    print(f"Added {len(background_paths)} background (empty-label) images to train")


def write_yolo_class_files(
    category_info: dict[int, dict], class_map: dict[int, int], output_dir: Path
) -> None:
    """class_mapping.json, classes.txt, dataset.yaml 을 shared_v2 데이터셋 루트에 저장합니다.

    Args:
        category_info: category_id -> {dl_name, item_seq}.
        class_map: category_id -> YOLO 클래스 인덱스 매핑.
        output_dir: shared_v2 데이터셋 루트 디렉토리.
    """
    with open(output_dir / "class_mapping.json", "w", encoding="utf-8") as f:
        json.dump(
            {str(cid): idx for cid, idx in class_map.items()}, f, indent=4, ensure_ascii=False
        )

    category_ids = sorted(category_info)
    with open(output_dir / "classes.txt", "w", encoding="utf-8") as f:
        for cid in category_ids:
            f.write(f"{category_info[cid]['dl_name']}\n")

    with open(output_dir / "dataset.yaml", "w", encoding="utf-8") as f:
        f.write(f"path: {output_dir.resolve()}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n\n")
        f.write("names:\n")
        for cid in category_ids:
            idx = class_map[cid]
            f.write(f"  {idx}: {category_info[cid]['dl_name']}\n")


def export_yolo_dataset(
    category_info: dict[int, dict],
    train_annot_dir: Path,
    train_images_dir: Path,
    output_dir: Path,
    backgrounds_dir: Path,
) -> None:
    """train_annotations/train_images 를 YOLO 데이터셋(images/labels + dataset.yaml)으로 변환합니다.

    src/util/shared_dataset_composer.py(v1) 와 동일하게 클래스 층화 train/val 분할 후
    배경(negative) 이미지를 추가합니다.

    Args:
        category_info: build_class_mapping 이 만든 category_id -> {dl_name, item_seq}.
        train_annot_dir: train_annotations 디렉토리.
        train_images_dir: train_images 디렉토리.
        output_dir: shared_v2 데이터셋을 저장할 루트 디렉토리.
        backgrounds_dir: 배경 이미지 중간 산출물을 저장할 디렉토리.
    """
    for p in [
        output_dir / "images/train",
        output_dir / "images/val",
        output_dir / "labels/train",
        output_dir / "labels/val",
    ]:
        p.mkdir(parents=True, exist_ok=True)

    category_ids = sorted(category_info)
    class_map = {cid: idx for idx, cid in enumerate(category_ids)}

    image_meta = collect_image_annotations(train_annot_dir)
    print(f"Total unique images: {len(image_meta)}")

    train_images, val_images = stratified_split(image_meta, class_map, TRAIN_RATIO, SEED)

    for mode, images in (("train", train_images), ("val", val_images)):
        present = Counter()
        for name in images:
            present.update(
                class_map[ann["category_id"]] for ann in image_meta[name]["anns"]
            )
        missing = [
            category_info[cid]["dl_name"] for cid in category_ids if class_map[cid] not in present
        ]
        print(
            f"{mode}: {len(images)} images, {len(present)}/{len(category_ids)} classes present"
            + (f", missing: {missing}" if missing else "")
        )

    convert_to_yolo(image_meta, class_map, train_images, "train", train_images_dir, output_dir)
    convert_to_yolo(image_meta, class_map, val_images, "val", train_images_dir, output_dir)
    add_background_images(image_meta, train_images_dir, output_dir, backgrounds_dir, NUM_BACKGROUNDS, SEED)

    write_yolo_class_files(category_info, class_map, output_dir)

    print("YOLO dataset export done!")


def main() -> None:
    TRAIN_ANNOT_DIR.mkdir(parents=True, exist_ok=True)
    TRAIN_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state(STATE_PATH)

    tl_tar_paths = sorted(p for p in RAW_V2_ROOT.glob("download_TL_*.tar") if TL_TAR_PATTERN.match(p.name))
    ts_tar_paths = sorted(p for p in RAW_V2_ROOT.glob("download_TS_*.tar") if TS_TAR_PATTERN.match(p.name))

    pending_tl = [
        p for p in tl_tar_paths
        if int(TL_TAR_PATTERN.match(p.name).group("index")) not in state["completed_tl_indices"]
    ]
    pending_ts = [
        p for p in ts_tar_paths
        if int(TS_TAR_PATTERN.match(p.name).group("index")) not in state["completed_ts_indices"]
    ]

    for tar_path in tqdm(pending_tl, desc="Extracting TL tars\t"):
        idx = int(TL_TAR_PATTERN.match(tar_path.name).group("index"))
        combo_count = _process_with_retry(process_tl_tar, tar_path, TRAIN_ANNOT_DIR)
        print(f"[{tar_path.name}] 콤보 라벨 폴더 {combo_count}개 추출")
        state["completed_tl_indices"].add(idx)
        save_state(state, STATE_PATH)

    for tar_path in tqdm(pending_ts, desc="Extracting TS tars\t"):
        idx = int(TS_TAR_PATTERN.match(tar_path.name).group("index"))
        image_count = _process_with_retry(process_ts_tar, tar_path, TRAIN_IMAGES_DIR)
        print(f"[{tar_path.name}] 이미지 {image_count}장 추출")
        state["completed_ts_indices"].add(idx)
        save_state(state, STATE_PATH)

    shutil.rmtree(WORK_DIR, ignore_errors=True)

    category_info, category_counts, invalid_bbox_files = build_class_mapping(TRAIN_ANNOT_DIR)
    write_class_mapping_csv(category_info, CLASS_MAPPING_PATH)
    write_class_count_md(category_info, category_counts, invalid_bbox_files, CLASS_COUNT_MD_PATH)

    print(f"Done! {len(category_info)} classes, {sum(category_counts.values())} annotations")

    export_yolo_dataset(category_info, TRAIN_ANNOT_DIR, TRAIN_IMAGES_DIR, YOLO_OUTPUT, BACKGROUNDS_DIR)


if __name__ == "__main__":
    main()