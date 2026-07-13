"""data/collect_single 에 내려받은 원본 이미지 데이터(원천데이터, ``TS_*``)에서
class_mapping.csv 의 category_id 에 해당하는 이미지만 걸러내 data/collect_single/processed 로
정리합니다.

TS_*.tar 는 파일 하나가 수십~90GB 이상으로 매우 커서, 한 번에 다 받아두고 처리하기 어렵습니다.
그래서 이 스크립트는 "TS_XX 하나 다운로드 -> 실행해서 처리 -> 원본 삭제 -> 다음 TS 다운로드"
흐름을 전제로 만들어졌습니다. collect_single 폴더에 존재하는 download_TS_*.tar 를 찾아 아직
처리하지 않은 것만 순서대로 처리하며, 하나 끝날 때마다 결과를 검증한 뒤 원본 tar 를 삭제해
디스크 공간을 확보합니다. (다운로드 중인 ``*.tar.crdownload`` 파일은 확장자가 달라 자동으로
건너뜁니다.)

collect_single_annotation_dataset.py 와 동일하게 tar 안에는 큰 zip 이 조각(``*.zip.part<offset>``)
으로 들어 있습니다. 다만 이미지 zip 은 라벨 zip과 달리 용량이 매우 크기 때문에, 전체를 디스크에
풀어내는 대신 tar 멤버를 직접 스트림으로 읽어 zip 의 중앙 디렉터리만 확인하고 필요한
category_id 에 해당하는 이미지 파일만 선택적으로 압축 해제합니다. (조각이 여러 개인 경우에만
어쩔 수 없이 임시 파일로 합칩니다.)

이미지 파일명(예: ``K-000059_0_0_0_0_60_000_200.png``)의 앞부분 K-코드에서 앞의 0 을 제거한
정수가 class_mapping.csv 의 category_id 와 대응합니다.

처리 결과로 다음을 만듭니다.
    - processed/images: 유효 category_id 이미지만 모아둔 폴더 (``K-<6자리코드>_png/*.png``).
    - processed/image_file_counts.md, .csv: 클래스별 이미지 개수.

tar 처리마다 processed/_image_state.json 에 진행 상황을 체크포인트로 남겨, 스크립트를 다시
실행하면 이미 처리한 TS 는 건너뜁니다.
"""

import csv
import json
import re
import shutil
import tarfile
import tempfile
import zipfile
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from tqdm import tqdm

COLLECT_SINGLE_ROOT = Path("../../data/collect_single")
CLASS_MAPPING_PATH = COLLECT_SINGLE_ROOT / "class_mapping.csv"

WORK_DIR = Path(tempfile.gettempdir()) / "collect_single_image_extract"

PROCESSED_ROOT = COLLECT_SINGLE_ROOT / "processed"
PROCESSED_IMAGES_DIR = PROCESSED_ROOT / "images"
IMAGE_COUNT_MD_PATH = PROCESSED_ROOT / "image_file_counts.md"
IMAGE_COUNT_CSV_PATH = PROCESSED_ROOT / "image_file_counts.csv"
STATE_PATH = PROCESSED_ROOT / "_image_state.json"

ZIP_PART_PATTERN = re.compile(r"^(?P<base>.+\.zip)\.part(?P<offset>\d+)$")
IMAGE_FILENAME_PATTERN = re.compile(r"^K-(?P<code>\d+)_.*\.png$", re.IGNORECASE)
TS_TAR_PATTERN = re.compile(r"^download_TS_(?P<index>\d+)\.tar$")


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


def _group_zip_parts(tar: tarfile.TarFile) -> dict[str, list[tarfile.TarInfo]]:
    """tar 안에 있는 zip.part<offset> 멤버를 zip 이름별로 묶어 offset 순으로 정렬합니다.

    Args:
        tar: 열려 있는 TarFile 객체.

    Returns:
        zip 파일명 -> offset 순으로 정렬된 TarInfo 목록.
    """
    parts_by_zip: dict[str, list[tarfile.TarInfo]] = defaultdict(list)
    for member in tar.getmembers():
        if not member.isfile():
            continue
        match = ZIP_PART_PATTERN.match(Path(member.name).name)
        if match is None:
            continue
        parts_by_zip[match.group("base")].append(member)

    for parts in parts_by_zip.values():
        parts.sort(key=lambda m: int(ZIP_PART_PATTERN.match(Path(m.name).name).group("offset")))

    return parts_by_zip


@contextmanager
def _open_zip_from_tar_members(tar: tarfile.TarFile, members: list[tarfile.TarInfo], work_dir: Path):
    """tar 멤버(zip 조각)를 ZipFile 로 엽니다.

    조각이 하나뿐이면 디스크에 복사하지 않고 tar 내부 스트림을 그대로 읽어(랜덤 액세스)
    ZipFile 을 엽니다. 대용량 이미지 zip 을 통째로 풀지 않기 위한 핵심 최적화입니다.
    조각이 여럿인 경우에만 어쩔 수 없이 임시 파일로 이어붙인 뒤 엽니다.

    Args:
        tar: 열려 있는 TarFile 객체.
        members: offset 순으로 정렬된 하나의 zip 에 대한 조각 목록.
        work_dir: 조각이 여러 개일 때 병합 파일을 만들어 둘 임시 디렉토리.

    Yields:
        열린 zipfile.ZipFile 객체.
    """
    if len(members) == 1:
        with tar.extractfile(members[0]) as stream, zipfile.ZipFile(stream) as zf:
            yield zf
        return

    work_dir.mkdir(parents=True, exist_ok=True)
    merged_path = work_dir / Path(members[0].name).name.split(".part")[0]
    with open(merged_path, "wb") as merged:
        for member in members:
            with tar.extractfile(member) as src:
                shutil.copyfileobj(src, merged)

    try:
        with zipfile.ZipFile(merged_path) as zf:
            yield zf
    finally:
        merged_path.unlink(missing_ok=True)


def process_ts_tar(
    tar_path: Path, class_table: dict[int, dict], processed_images_dir: Path
) -> tuple[set[int], dict[int, int]]:
    """tar 안 zip 의 중앙 디렉터리만 읽어, 유효 category_id 이미지만 선택적으로 압축 해제합니다.

    Args:
        tar_path: download_TS_*.tar 파일 경로.
        class_table: category_id -> {class_index, class_name} 매핑.
        processed_images_dir: 정리된 이미지를 모아둘 대상 디렉토리.

    Returns:
        (matched_category_ids, file_counts) 튜플.
        matched_category_ids: 이 tar 에서 발견된 유효 category_id 집합.
        file_counts: 이 tar 에서 옮겨진 category_id 별 이미지 파일 수.
    """
    matched_category_ids: set[int] = set()
    file_counts: dict[int, int] = defaultdict(int)

    with tarfile.open(tar_path) as tar:
        parts_by_zip = _group_zip_parts(tar)

        for members in parts_by_zip.values():
            with _open_zip_from_tar_members(tar, members, WORK_DIR) as zf:
                image_infos: list[tuple[zipfile.ZipInfo, int]] = []
                for info in zf.infolist():
                    if info.filename.endswith("/"):
                        continue
                    match = IMAGE_FILENAME_PATTERN.match(Path(info.filename).name)
                    if match is None:
                        continue
                    image_infos.append((info, int(match.group("code"))))

                for info, category_id in tqdm(
                    image_infos, desc=f"Extracting matched images ({tar_path.name})\t", leave=False
                ):
                    filename = Path(info.filename).name
                    if category_id not in class_table:
                        continue

                    matched_category_ids.add(category_id)

                    dest_dir = processed_images_dir / f"K-{category_id:06d}_png"
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    dest_path = dest_dir / filename

                    with zf.open(info) as src, open(dest_path, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    file_counts[category_id] += 1

    return matched_category_ids, file_counts


def _process_ts_tar_with_retry(
    tar_path: Path, class_table: dict[int, dict], processed_images_dir: Path, max_attempts: int = 3
) -> tuple[set[int], dict[int, int]]:
    """process_ts_tar 를 실행하되, 일시적인 I/O 오류가 나면 최대 max_attempts 번 재시도합니다.

    Args:
        tar_path: download_TS_*.tar 파일 경로.
        class_table: category_id -> {class_index, class_name} 매핑.
        processed_images_dir: 정리된 이미지를 모아둘 대상 디렉토리.
        max_attempts: 최대 재시도 횟수.

    Returns:
        process_ts_tar 와 동일한 (matched_category_ids, file_counts) 튜플.
    """
    for attempt in range(1, max_attempts + 1):
        try:
            return process_ts_tar(tar_path, class_table, processed_images_dir)
        except (zipfile.BadZipFile, EOFError, OSError, tarfile.ReadError):
            if attempt == max_attempts:
                raise
            print(f"[{tar_path.name}] 처리 중 오류 발생, 재시도 ({attempt}/{max_attempts})")

    raise AssertionError("unreachable")


def verify_extracted_images(processed_images_dir: Path, file_counts: dict[int, int]) -> bool:
    """방금 옮긴 category_id 별 이미지 개수가 실제 디스크 상태와 일치하는지 확인합니다.

    Args:
        processed_images_dir: 정리된 이미지가 있는 디렉토리.
        file_counts: 이번 tar 에서 옮겨진 category_id 별 이미지 파일 수.

    Returns:
        모든 category_id 폴더의 실제 파일 수가 file_counts 와 일치하면 True.
    """
    for category_id, expected_count in file_counts.items():
        dest_dir = processed_images_dir / f"K-{category_id:06d}_png"
        actual_count = sum(1 for _ in dest_dir.glob("*.png"))
        if actual_count != expected_count:
            return False
    return True


def load_state(path: Path) -> dict:
    """이전 실행에서 남긴 체크포인트를 읽어옵니다. 없으면 빈 상태를 반환합니다.

    Args:
        path: _image_state.json 경로.

    Returns:
        completed_ts_indices/matched_ts_indices/file_counts 를 담은 상태 딕셔너리.
    """
    if not path.exists():
        return {"completed_ts_indices": set(), "matched_ts_indices": set(), "file_counts": defaultdict(int)}

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    file_counts = defaultdict(int)
    for category_id, count in raw.get("file_counts", {}).items():
        file_counts[int(category_id)] = count

    return {
        "completed_ts_indices": set(raw.get("completed_ts_indices", [])),
        "matched_ts_indices": set(raw.get("matched_ts_indices", [])),
        "file_counts": file_counts,
    }


def save_state(state: dict, path: Path) -> None:
    """진행 상황을 _image_state.json 에 체크포인트로 저장합니다.

    Args:
        state: completed_ts_indices/matched_ts_indices/file_counts 를 담은 상태 딕셔너리.
        path: _image_state.json 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {
        "completed_ts_indices": sorted(state["completed_ts_indices"]),
        "matched_ts_indices": sorted(state["matched_ts_indices"]),
        "file_counts": {str(cid): count for cid, count in state["file_counts"].items()},
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def write_image_count_md(class_table: dict[int, dict], total_file_counts: dict[int, int], path: Path) -> None:
    """클래스별 이미지 파일 개수를 markdown 표로 정리합니다.

    Args:
        class_table: category_id -> {class_index, class_name} 매핑.
        total_file_counts: category_id -> 옮겨진 이미지 파일 수.
        path: 결과를 저장할 md 파일 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    found_classes = sum(1 for cid in class_table if total_file_counts.get(cid, 0) > 0)
    lines = [
        "# collect_single 클래스별 이미지 파일 개수",
        "",
        f"- class_mapping.csv 기준 전체 클래스 수: {len(class_table)}",
        f"- 이미지가 존재하는 클래스 수: {found_classes}",
        f"- 전체 이미지 파일 수: {sum(total_file_counts.values())}",
        "",
        "| category_id | class_index | class_name | file_count |",
        "|---|---|---|---|",
    ]
    for category_id, info in sorted(class_table.items(), key=lambda kv: kv[1]["class_index"]):
        count = total_file_counts.get(category_id, 0)
        lines.append(f"| {category_id} | {info['class_index']} | {info['class_name']} | {count} |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_image_count_csv(class_table: dict[int, dict], total_file_counts: dict[int, int], path: Path) -> None:
    """클래스별 이미지 파일 개수를 csv 로 정리합니다.

    Args:
        class_table: category_id -> {class_index, class_name} 매핑.
        total_file_counts: category_id -> 옮겨진 이미지 파일 수.
        path: 결과를 저장할 csv 파일 경로.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["category_id", "class_index", "class_name", "file_count"])
        for category_id, info in sorted(class_table.items(), key=lambda kv: kv[1]["class_index"]):
            count = total_file_counts.get(category_id, 0)
            writer.writerow([category_id, info["class_index"], info["class_name"], count])


def main() -> None:
    class_table = load_class_table(CLASS_MAPPING_PATH)
    PROCESSED_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    state = load_state(STATE_PATH)

    ts_tar_paths = sorted(p for p in COLLECT_SINGLE_ROOT.glob("download_TS_*.tar") if TS_TAR_PATTERN.match(p.name))
    pending_tar_paths = [
        tar_path
        for tar_path in ts_tar_paths
        if int(TS_TAR_PATTERN.match(tar_path.name).group("index")) not in state["completed_ts_indices"]
    ]

    if not pending_tar_paths:
        print("처리할 새 download_TS_*.tar 가 없습니다. (다운로드 중인 *.tar.crdownload 는 완료 후 다시 실행하세요.)")

    for tar_path in pending_tar_paths:
        ts_index = int(TS_TAR_PATTERN.match(tar_path.name).group("index"))
        size_gib = tar_path.stat().st_size / 1024**3
        print(f"[{tar_path.name}] 처리 시작 ({size_gib:.2f} GiB)")

        matched_category_ids, file_counts = _process_ts_tar_with_retry(tar_path, class_table, PROCESSED_IMAGES_DIR)

        if not verify_extracted_images(PROCESSED_IMAGES_DIR, file_counts):
            raise RuntimeError(f"[{tar_path.name}] 추출 결과 검증 실패 - 원본 tar 를 삭제하지 않고 중단합니다.")

        if matched_category_ids:
            state["matched_ts_indices"].add(ts_index)
        for category_id, count in file_counts.items():
            state["file_counts"][category_id] += count
        state["completed_ts_indices"].add(ts_index)
        save_state(state, STATE_PATH)

        tar_path.unlink()
        print(
            f"[{tar_path.name}] 처리 완료: {len(matched_category_ids)}개 클래스, "
            f"{sum(file_counts.values())}장 추출. 원본 tar 삭제함."
        )

    shutil.rmtree(WORK_DIR, ignore_errors=True)

    write_image_count_md(class_table, state["file_counts"], IMAGE_COUNT_MD_PATH)
    write_image_count_csv(class_table, state["file_counts"], IMAGE_COUNT_CSV_PATH)


if __name__ == "__main__":
    main()
