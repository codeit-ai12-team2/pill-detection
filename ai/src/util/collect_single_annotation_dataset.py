"""data/collect_single 에 내려받은 원본 라벨링 데이터를 풀어서 class_mapping.csv 의
category_id 에 해당하는 항목만 걸러낸 뒤 data/collect_single/processed 로 정리합니다.

collect_single 폴더에는 AI Hub "약품식별" 데이터셋의 라벨링데이터(``download_TL_*.tar``)만
내려받아져 있고, 이미지 원본(원천데이터, ``TS_*``)은 아직 없습니다. tar 안의 zip
(``*.zip.part<offset>``)을 풀면 ``K-<6자리코드>_json/`` 폴더가 나오는데, 이 코드에서 앞의
0 을 제거한 정수가 class_mapping.csv 의 category_id 와 대응합니다.

처리 결과로 다음을 만듭니다.
    - processed/labels: 유효 category_id 라벨만 정규화(annotation 의 category_id/name 을
      실제 약물 정보로 교정)해서 모아둔 폴더.
    - processed/class_file_counts.md: 클래스별 라벨 파일(json) 개수.
    - processed/required_downloads.md: 라벨이 발견된 TL 번호에 대응하는 이미지 원본(TS_*)
      다운로드 목록과, class_mapping.csv 에는 있지만 라벨을 전혀 찾지 못한 category_id 목록.

tar 81개(총 수 GB)를 순서대로 풀다 보면 실행 환경의 시간 제한 등으로 중간에 중단될 수 있어,
tar 하나를 처리할 때마다 processed/_state.json 에 진행 상황을 체크포인트로 남깁니다. 스크립트를
다시 실행하면 이미 완료된 tar 는 건너뛰고 남은 tar 부터 이어서 처리합니다.

중간 압축 해제 작업 공간(WORK_DIR)은 원본 데이터가 있는 드라이브가 아닌 시스템 임시 폴더를
사용합니다. (원본 드라이브에 직접 압축을 풀면 대용량 연속 쓰기 중 간헐적인 EOFError 가
발생하는 것을 확인했습니다.)
"""

import csv
import json
import re
import shutil
import tarfile
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

from tqdm import tqdm

COLLECT_SINGLE_ROOT = Path("../../data/collect_single")
CLASS_MAPPING_PATH = COLLECT_SINGLE_ROOT / "class_mapping.csv"

WORK_DIR = Path(tempfile.gettempdir()) / "collect_single_extract"

PROCESSED_ROOT = COLLECT_SINGLE_ROOT / "processed"
PROCESSED_LABELS_DIR = PROCESSED_ROOT / "labels"
CLASS_COUNT_MD_PATH = PROCESSED_ROOT / "class_file_counts.md"
CLASS_COUNT_CSV_PATH = PROCESSED_ROOT / "class_file_counts.csv"
REQUIRED_DOWNLOADS_MD_PATH = PROCESSED_ROOT / "required_downloads.md"
STATE_PATH = PROCESSED_ROOT / "_state.json"

ZIP_PART_PATTERN = re.compile(r"^(?P<base>.+\.zip)\.part(?P<offset>\d+)$")
KCODE_DIR_PATTERN = re.compile(r"^K-(?P<code>\d+)_json$")
TL_TAR_PATTERN = re.compile(r"^download_TL_(?P<index>\d+)\.tar$")


def load_class_table(csv_path: Path) -> dict[int, dict]:
    """class_mapping.csv 를 읽어 category_id -> {class_index, class_name} 매핑을 만듭니다.

    Args:
        csv_path: class_mapping.csv 파일 경로.

    Returns:
        category_id 를 key 로 갖고, class_index/class_name 을 담은 dict 를 value 로 갖는 딕셔너리.
    """
    class_table = {}
    with open(csv_path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            class_table[int(row["category_id"])] = {
                "class_index": int(row["class_index"]),
                "class_name": row["dl_name"],
            }
    return class_table


def extract_tar(tar_path: Path, extract_dir: Path) -> None:
    """tar 파일 하나를 풀어, 그 안의 분할 zip 조각을 offset 순서로 이어붙인 뒤 extract_dir 에 풉니다.

    Args:
        tar_path: download_TL_*.tar 파일 경로.
        extract_dir: 압축을 풀어낼 대상 디렉토리.
    """
    extract_dir.mkdir(parents=True, exist_ok=True)
    tar_work_dir = extract_dir / f"_{tar_path.stem}_raw"
    tar_work_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(tar_path) as tar:
        tar.extractall(tar_work_dir, filter="data")

    parts_by_zip: dict[str, list[Path]] = defaultdict(list)
    for part_path in tar_work_dir.rglob("*.zip.part*"):
        match = ZIP_PART_PATTERN.match(part_path.name)
        if match is None:
            continue
        parts_by_zip[match.group("base")].append(part_path)

    for zip_name, parts in parts_by_zip.items():
        parts.sort(key=lambda p: int(ZIP_PART_PATTERN.match(p.name).group("offset")))

        merged_zip_path = tar_work_dir / zip_name
        with open(merged_zip_path, "wb") as merged:
            for part_path in parts:
                with open(part_path, "rb") as part_f:
                    shutil.copyfileobj(part_f, merged)

        with zipfile.ZipFile(merged_zip_path) as zf:
            zf.extractall(extract_dir)

    shutil.rmtree(tar_work_dir)


def _normalize_annotation(json_path: Path, category_id: int, category_name: str) -> None:
    """어노테이션 json 의 category_id/name 을 실제 약물 정보로 바로잡습니다.

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


def process_tar(
    tar_path: Path, class_table: dict[int, dict], processed_labels_dir: Path
) -> tuple[set[int], dict[int, int]]:
    """tar 하나를 풀어 유효 category_id 폴더만 정규화한 뒤 processed_labels_dir 로 옮깁니다.

    Args:
        tar_path: download_TL_*.tar 파일 경로.
        class_table: category_id -> {class_index, class_name} 매핑.
        processed_labels_dir: 정리된 라벨을 모아둘 대상 디렉토리.

    Returns:
        (matched_category_ids, file_counts) 튜플.
        matched_category_ids: 이 tar 에서 발견된 유효 category_id 집합.
        file_counts: 이 tar 에서 옮겨진 category_id 별 json 파일 수.
    """
    extract_dir = WORK_DIR / tar_path.stem

    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        shutil.rmtree(extract_dir, ignore_errors=True)
        try:
            extract_tar(tar_path, extract_dir)
            break
        except (zipfile.BadZipFile, EOFError, OSError):
            if attempt == max_attempts:
                raise

    matched_category_ids: set[int] = set()
    file_counts: dict[int, int] = defaultdict(int)

    kcode_dirs = [p for p in extract_dir.rglob("K-*_json") if p.is_dir()]
    for kcode_dir in kcode_dirs:
        match = KCODE_DIR_PATTERN.match(kcode_dir.name)
        if match is None:
            continue

        category_id = int(match.group("code"))
        if category_id not in class_table:
            continue

        matched_category_ids.add(category_id)
        class_name = class_table[category_id]["class_name"]

        json_paths = list(kcode_dir.glob("*.json"))
        for json_path in json_paths:
            _normalize_annotation(json_path, category_id, class_name)
        file_counts[category_id] += len(json_paths)

        destination = processed_labels_dir / kcode_dir.name
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(str(kcode_dir), str(destination))

    shutil.rmtree(extract_dir)
    return matched_category_ids, file_counts


def load_state(path: Path) -> dict:
    """이전 실행에서 남긴 체크포인트를 읽어옵니다. 없으면 빈 상태를 반환합니다.

    Args:
        path: _state.json 경로.

    Returns:
        completed_tar_indices/matched_tar_indices/file_counts 를 담은 상태 딕셔너리.
    """
    if not path.exists():
        return {"completed_tar_indices": set(), "matched_tar_indices": set(), "file_counts": defaultdict(int)}

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    file_counts = defaultdict(int)
    for category_id, count in raw.get("file_counts", {}).items():
        file_counts[int(category_id)] = count

    return {
        "completed_tar_indices": set(raw.get("completed_tar_indices", [])),
        "matched_tar_indices": set(raw.get("matched_tar_indices", [])),
        "file_counts": file_counts,
    }


def save_state(state: dict, path: Path) -> None:
    """진행 상황을 _state.json 에 체크포인트로 저장합니다.

    Args:
        state: completed_tar_indices/matched_tar_indices/file_counts 를 담은 상태 딕셔너리.
        path: _state.json 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        "completed_tar_indices": sorted(state["completed_tar_indices"]),
        "matched_tar_indices": sorted(state["matched_tar_indices"]),
        "file_counts": {str(cid): count for cid, count in state["file_counts"].items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def write_class_count_md(
    class_table: dict[int, dict], total_file_counts: dict[int, int], path: Path
) -> None:
    """클래스별 라벨 파일 개수를 markdown 표로 정리합니다.

    Args:
        class_table: category_id -> {class_index, class_name} 매핑.
        total_file_counts: category_id -> 옮겨진 json 파일 수.
        path: 결과를 저장할 md 파일 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    found_classes = sum(1 for cid in class_table if total_file_counts.get(cid, 0) > 0)
    lines = [
        "# collect_single 클래스별 라벨 파일 개수",
        "",
        f"- class_mapping.csv 기준 전체 클래스 수: {len(class_table)}",
        f"- 라벨이 존재하는 클래스 수: {found_classes}",
        f"- 전체 라벨 파일 수: {sum(total_file_counts.values())}",
        "",
        "| category_id | class_index | class_name | file_count |",
        "|---|---|---|---|",
    ]
    for category_id, info in sorted(class_table.items(), key=lambda kv: kv[1]["class_index"]):
        count = total_file_counts.get(category_id, 0)
        lines.append(f"| {category_id} | {info['class_index']} | {info['class_name']} | {count} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_class_count_csv(
    class_table: dict[int, dict], total_file_counts: dict[int, int], path: Path
) -> None:
    """클래스별 라벨 파일 개수를 csv 로 정리합니다.

    Args:
        class_table: category_id -> {class_index, class_name} 매핑.
        total_file_counts: category_id -> 옮겨진 json 파일 수.
        path: 결과를 저장할 csv 파일 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["category_id", "class_index", "class_name", "file_count"])
        for category_id, info in sorted(class_table.items(), key=lambda kv: kv[1]["class_index"]):
            count = total_file_counts.get(category_id, 0)
            writer.writerow([category_id, info["class_index"], info["class_name"], count])


def write_required_downloads_md(
    class_table: dict[int, dict],
    total_file_counts: dict[int, int],
    matched_tar_indices: set[int],
    all_tar_indices: set[int],
    path: Path,
    incomplete: bool = False,
) -> None:
    """추가로 받아야 하는 이미지 원본(TS_*) 목록과 라벨을 전혀 찾지 못한 클래스를 정리합니다.

    AI Hub 원본 데이터셋에서 TS_N(원천데이터)과 TL_N(라벨링데이터)은 동일한 번호가 동일한
    약물 subset 을 가리킨다는 전제 하에, 유효 category_id 라벨이 실제로 존재했던 TL 번호와
    같은 번호의 TS 파일을 다운로드 대상으로 안내합니다.

    Args:
        class_table: category_id -> {class_index, class_name} 매핑.
        total_file_counts: category_id -> 옮겨진 json 파일 수(전체 tar 합산).
        matched_tar_indices: 유효 category_id 라벨이 하나라도 있었던 TL 번호 집합.
        all_tar_indices: collect_single 폴더에 존재하는 전체 TL 번호 집합.
        path: 결과를 저장할 md 파일 경로.
        incomplete: 아직 모든 tar 를 처리하지 못한 중간 상태인지 여부.
    """
    missing_category_ids = sorted(cid for cid in class_table if total_file_counts.get(cid, 0) == 0)
    expected_tar_range = set(range(min(all_tar_indices), max(all_tar_indices) + 1)) if all_tar_indices else set()
    gap_tar_indices = sorted(expected_tar_range - all_tar_indices)

    lines = [
        "# 추가로 받아야 하는 파일 목록",
        "",
        "collect_single 에는 라벨링데이터(`TL_*`)만 내려받아져 있고 이미지 원본(원천데이터,",
        "`TS_*`)은 없습니다. 아래 목록은 유효 category_id 라벨이 실제로 존재했던 TL 번호를",
        "기준으로, 짝이 되는 이미지 zip(`TS_*`)을 추가로 내려받아야 함을 나타냅니다.",
        "(AI Hub 원본에서 TS_N 과 TL_N 은 동일한 약물 subset 을 담고 있다는 전제)",
        "",
        "## 이미지 원본(TS_*) 다운로드 필요 목록",
        "",
    ]
    if matched_tar_indices:
        for idx in sorted(matched_tar_indices):
            lines.append(f"- TS_{idx}_단일.zip (download_TS_{idx:02d}.tar)")
    else:
        lines.append("- 없음")

    lines += [
        "",
        "## class_mapping.csv 에는 있으나 collect_single 라벨에서 전혀 찾지 못한 category_id",
        "",
    ]
    if missing_category_ids:
        lines.append("| category_id | class_index | class_name |")
        lines.append("|---|---|---|")
        for cid in missing_category_ids:
            info = class_table[cid]
            lines.append(f"| {cid} | {info['class_index']} | {info['class_name']} |")
    else:
        lines.append("- 없음 (전체 category_id 라벨을 모두 찾음)")

    lines += [
        "",
        "## 로컬에 존재하지 않는 TL 번호 (다운로드받은 번호 사이의 결번)",
        "",
    ]
    if gap_tar_indices:
        lines.append(", ".join(f"TL_{idx}" for idx in gap_tar_indices))
    elif all_tar_indices:
        lines.append(f"- 없음 (download_TL_{min(all_tar_indices):02d}.tar ~ download_TL_{max(all_tar_indices):02d}.tar 사이에 결번 없음)")
    else:
        lines.append("- download_TL_*.tar 파일을 하나도 찾지 못했습니다.")

    if incomplete:
        lines += [
            "",
            "> ⚠️ 아직 모든 TL tar 를 처리하지 못한 중간 상태입니다. "
            "스크립트를 다시 실행하면 남은 tar 부터 이어서 처리합니다.",
        ]

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    class_table = load_class_table(CLASS_MAPPING_PATH)

    PROCESSED_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    tar_paths = sorted(COLLECT_SINGLE_ROOT.glob("download_TL_*.tar"))
    all_tar_indices = {
        int(match.group("index"))
        for match in (TL_TAR_PATTERN.match(p.name) for p in tar_paths)
        if match is not None
    }

    state = load_state(STATE_PATH)
    remaining_tar_paths = [
        tar_path
        for tar_path in tar_paths
        if TL_TAR_PATTERN.match(tar_path.name)
        and int(TL_TAR_PATTERN.match(tar_path.name).group("index")) not in state["completed_tar_indices"]
    ]

    for tar_path in tqdm(remaining_tar_paths, desc="Processing TL tars\t"):
        tar_index = int(TL_TAR_PATTERN.match(tar_path.name).group("index"))

        matched_category_ids, file_counts = process_tar(tar_path, class_table, PROCESSED_LABELS_DIR)
        if matched_category_ids:
            state["matched_tar_indices"].add(tar_index)
        for category_id, count in file_counts.items():
            state["file_counts"][category_id] += count
        state["completed_tar_indices"].add(tar_index)

        save_state(state, STATE_PATH)

    shutil.rmtree(WORK_DIR, ignore_errors=True)

    incomplete = state["completed_tar_indices"] != all_tar_indices
    write_class_count_md(class_table, state["file_counts"], CLASS_COUNT_MD_PATH)
    write_class_count_csv(class_table, state["file_counts"], CLASS_COUNT_CSV_PATH)
    write_required_downloads_md(
        class_table,
        state["file_counts"],
        state["matched_tar_indices"],
        all_tar_indices,
        REQUIRED_DOWNLOADS_MD_PATH,
        incomplete=incomplete,
    )


if __name__ == "__main__":
    main()
