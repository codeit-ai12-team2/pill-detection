# ai/src/util

알약 데이터셋을 원본(다운로드 tar/zip)에서 학습에 쓸 수 있는 형태로 가공하는 스크립트 모음입니다.

모든 스크립트는 경로를 `Path("../../data/...")` 형태의 **상대 경로**로 잡고 있으므로, 반드시
`ai/src/util` 디렉토리에서 실행해야 합니다 (`cd ai/src/util && python <script>.py`). 아래
디렉토리 트리의 최상위 `data/`는 실제로는 `ai/data/`를 가리킵니다.

대략적인 파이프라인 흐름:

```
data/collect, data/collect_single (원본 다운로드)
        │
        ├─ collect_dataset_merger.py            ─┐
        ├─ collect_single_annotation_dataset.py  ─┼─▶ data/raw/{train_images,train_annotations}
        └─ collect_single_image_dataset.py       ─┘        (일부는 processed/ 에 남음)
                        │
                        ├─ background_extractor.py ──▶ data/processed/backgrounds
                        │
                        └─ shared_dataset_composer.py ──▶ data/processed/shared (YOLO 데이터셋)
```

---

## background_extractor.py

`data/raw/train_images`에서 일부 이미지를 뽑아, `train_annotations`의 bbox로 알약 영역을
`cv2.inpaint`로 지워 "알약이 없는 배경 이미지"를 만듭니다. `shared_dataset_composer.py`가 이
배경 이미지를 negative(빈 라벨) 샘플로 재사용합니다.

### 필요한 디렉토리 구조 (입력)

```
data/raw/
├── train_images/
│   └── <file_name>.png                 # json 의 images[0].file_name 과 동일해야 함
└── train_annotations/
    └── **/*.json                       # 하위 폴더 구조는 무관 (rglob 으로 전체 탐색)
        # 각 json 구조:
        # {
        #   "images": [{"file_name": ..., ...}],
        #   "annotations": [{"bbox": [x, y, w, h], ...}, ...]
        # }
```

### 만들어지는 결과물 (출력)

```
data/processed/backgrounds/
└── background_01.png ~ background_30.png   # NUM_BACKGROUNDS(기본 30)장
```

### 함수

| 함수 | 설명 | 인자 | 반환값 |
|---|---|---|---|
| `collect_image_bboxes(annot_root)` | 모든 라벨 json을 읽어 `image_name -> bbox 목록` 매핑 생성. 한 이미지에 여러 알약이 찍혀 라벨이 category별 폴더에 나뉜 경우까지 합침 | `annot_root: Path` | `dict[str, list[list[float]]]` |
| `build_mask(shape, bboxes, padding)` | bbox 영역(+padding)을 255로 채운 inpaint용 마스크 생성 | `shape, bboxes, padding` | `np.ndarray` |
| `select_background_images(image_bboxes, num_backgrounds, seed)` | 알약이 있는 이미지 중 배경으로 만들 이미지를 무작위 샘플링 | `image_bboxes, num_backgrounds, seed` | `list[str]` (파일명 목록) |
| `extract_backgrounds(image_names, image_root, image_bboxes, output_dir)` | 선택된 이미지에서 알약 영역을 inpaint로 지우고 `output_dir`에 저장 | `image_names, image_root, image_bboxes, output_dir` | `list[Path]` (저장된 경로) |
| `main()` | 위 함수들을 순서대로 실행하는 진입점 | - | - |

---

## collect_dataset_merger.py

`data/collect`에 내려받은 **조합 알약(combo)** 원본 압축 데이터를 풀어서, `class_table.csv`의
`category_id`에 해당하는 항목만 걸러낸 뒤 `data/raw/train_images`, `data/raw/train_annotations`로
옮깁니다. tar 안 zip이 여러 조각(`*.zip.part<byte offset>`)으로 분할되어 있어 offset 순서대로
이어붙인 뒤 압축을 풉니다.

### 필요한 디렉토리 구조 (입력)

```
data/collect/
├── class_table.csv            # 컬럼: category_id, class_index, class_name
├── images/
│   └── *.tar                  # 안에 <조합명>.zip.part<offset> 조각들
└── labels/
    └── *.tar                  # 안에 <조합명>.zip.part<offset> 조각들
                                # 압축 풀면 K-xxxxxx-xxxxxx-..._json/ 폴더 (콤보 = 여러 category_id 조합)
```

### 만들어지는 결과물 (출력)

```
data/raw/
├── train_images/
│   └── K-xxxxxx-...(콤보명)_..._200.png       # 유효 category만 남음, 이름 그대로 이동
└── train_annotations/
    └── K-xxxxxx-...(콤보명)_json/
        └── <category_dir>/*.json               # category_id/name이 실제 약물 정보로 정규화됨
```

처리 중 `data/collect/_extracted`(작업용 임시 폴더)를 만들며, 끝나면 자동 삭제합니다.

### 함수

| 함수 | 설명 | 인자 | 반환값 |
|---|---|---|---|
| `load_class_table(csv_path)` | `class_table.csv` → `category_id -> class_name` 매핑 생성 | `csv_path: Path` | `dict[int, str]` |
| `extract_archives(tar_dir, target_dir)` | `tar_dir`의 모든 tar를 풀고, 분할 zip 조각을 합쳐서 `target_dir`에 압축 해제 | `tar_dir, target_dir` | - |
| `parse_component_category_ids(combo_name)` | 콤보 이름(`K-000250-000573-...`)에서 개별 `category_id` 목록 추출 | `combo_name: str` | `list[int]` |
| `remove_invalid_categories(labels_dir, images_dir, valid_category_ids)` | 콤보를 구성하는 category_id 중 하나라도 유효하지 않으면 해당 콤보 라벨/이미지 삭제 | `labels_dir, images_dir, valid_category_ids` | - |
| `_normalize_annotation(json_path, category_id, category_name)` | json의 `category_id`/`name`을 실제 약물 정보로 교정 후 4-space indent로 재저장 | `json_path, category_id, category_name` | - |
| `move_filtered_data(labels_dir, images_dir, raw_annotations_dir, raw_images_dir, class_table)` | 필터링된 라벨/이미지를 정규화하며 `data/raw`로 이동 | 위 5개 | - |
| `main()` | 위 함수들을 순서대로 실행하는 진입점 | - | - |

---

## collect_single_annotation_dataset.py

`data/collect_single`에 내려받은 **단일 알약** 라벨링 데이터(`download_TL_*.tar`)를 풀어서
`class_mapping.csv`의 `category_id`에 해당하는 항목만 걸러낸 뒤 `data/collect_single/processed`로
정리합니다. `collect_single` 폴더에는 라벨링데이터(TL)만 있고 이미지 원본(TS)은 아직 없다는
전제로 만들어졌습니다.

tar 81개(총 수 GB)를 순서대로 풀다 보면 중간에 중단될 수 있어, tar 하나를 처리할 때마다
`processed/_state.json`에 체크포인트를 남깁니다. **다시 실행하면 `completed_tar_indices`에 이미
들어있는 tar는 건너뜁니다** — `class_mapping.csv` 내용을 바꿔서 새 category_id를 추가로 뽑고
싶다면, 해당 category_id가 들어있는 tar 번호를 `_state.json`의 `completed_tar_indices`에서
지운 뒤 다시 실행해야 합니다.

### 필요한 디렉토리 구조 (입력)

```
data/collect_single/
├── class_mapping.csv           # 컬럼: class_index, dl_name, category_id, item_seq
└── download_TL_<NN>.tar        # 라벨링데이터. 안에 TL_<N>_단일.zip.part<offset> 포함
                                 # 압축 풀면 K-<6자리코드>_json/*.json
```

### 만들어지는 결과물 (출력)

```
data/collect_single/processed/
├── labels/
│   └── K-<6자리코드>_json/
│       └── *.json                    # category_id/name이 실제 약물 정보로 정규화됨
├── class_file_counts.md              # 클래스별 라벨 파일(json) 개수 표
├── class_file_counts.csv             # 위와 동일 내용의 csv
├── required_downloads.md             # 라벨을 찾은 TL 번호에 대응하는 TS_* 다운로드 안내,
│                                      # class_mapping.csv엔 있지만 라벨을 못 찾은 category_id 목록
└── _state.json                       # 체크포인트: completed_tar_indices / matched_tar_indices / file_counts
```

(압축 해제 작업 공간은 원본 드라이브가 아닌 시스템 임시 폴더 `%TEMP%/collect_single_extract`를
사용하고, 처리 후 삭제됩니다.)

### 함수

| 함수 | 설명 | 인자 | 반환값 |
|---|---|---|---|
| `load_class_table(csv_path)` | `class_mapping.csv` → `category_id -> {class_index, class_name}` 매핑 생성 | `csv_path: Path` | `dict[int, dict]` |
| `extract_tar(tar_path, extract_dir)` | tar 하나를 풀고, 분할 zip 조각을 offset 순으로 이어붙여 `extract_dir`에 압축 해제 | `tar_path, extract_dir` | - |
| `_normalize_annotation(json_path, category_id, category_name)` | json의 `category_id`/`name`을 실제 약물 정보로 교정 | `json_path, category_id, category_name` | - |
| `process_tar(tar_path, class_table, processed_labels_dir)` | tar 하나를 풀어 유효 category_id 폴더만 정규화 후 `processed_labels_dir`로 이동 | `tar_path, class_table, processed_labels_dir` | `(matched_category_ids, file_counts)` |
| `load_state(path)` / `save_state(state, path)` | `_state.json` 체크포인트 로드/저장 | `path` / `state, path` | `dict` / - |
| `write_class_count_md/csv(...)` | 클래스별 라벨 파일 개수를 md/csv로 기록 | `class_table, total_file_counts, path` | - |
| `write_required_downloads_md(...)` | 추가로 받아야 할 `TS_*` 목록과 라벨을 못 찾은 category_id를 md로 기록 | `class_table, total_file_counts, matched_tar_indices, all_tar_indices, path, incomplete` | - |
| `main()` | 미완료 tar만 순서대로 처리하며 체크포인트를 남기는 진입점 | - | - |

---

## collect_single_image_dataset.py

`data/collect_single`에 내려받은 이미지 원본(원천데이터, `download_TS_*.tar`)에서
`class_mapping.csv`의 `category_id`에 해당하는 이미지만 걸러내 `data/collect_single/processed`로
정리합니다. `TS_*.tar`는 파일 하나가 수십~90GB 이상으로 매우 커서 **"TS 하나 다운로드 → 실행해서
처리 → 원본 삭제 → 다음 TS 다운로드"** 흐름을 전제로 만들어졌습니다. 이미지 zip은 라벨 zip과 달리
용량이 매우 커서, 전체를 디스크에 풀지 않고 tar 멤버를 스트림으로 읽어 zip 중앙 디렉터리만
확인한 뒤 필요한 category_id 이미지만 선택적으로 압축 해제합니다.

### 필요한 디렉토리 구조 (입력)

```
data/collect_single/
├── class_mapping.csv            # 컬럼: class_index, dl_name, category_id, item_seq
└── download_TS_<NN>.tar         # 이미지 원본. 안에 TS_<N>_단일.zip.part<offset> 포함
                                  # (다운로드 중인 *.tar.crdownload 는 자동으로 건너뜀)
```

### 만들어지는 결과물 (출력)

```
data/collect_single/processed/
├── images/
│   └── K-<6자리코드>_png/
│       └── *.png                     # 유효 category_id 이미지만
├── image_file_counts.md              # 클래스별 이미지 개수 표
├── image_file_counts.csv             # 위와 동일 내용의 csv
└── _image_state.json                 # 체크포인트: completed_ts_indices / matched_ts_indices / file_counts
```

**주의**: 처리가 끝난 `download_TS_*.tar` 원본은 검증(`verify_extracted_images`) 후 디스크 공간
확보를 위해 자동으로 삭제됩니다(`tar_path.unlink()`). 검증에 실패하면 원본을 지우지 않고
`RuntimeError`로 중단합니다.

### 함수

| 함수 | 설명 | 인자 | 반환값 |
|---|---|---|---|
| `load_class_table(csv_path)` | `class_mapping.csv` → `category_id -> {class_index, class_name}` 매핑 생성 | `csv_path: Path` | `dict[int, dict]` |
| `_group_zip_parts(tar)` | tar 안 `*.zip.part<offset>` 멤버를 zip 이름별로 묶어 offset 순 정렬 | `tar: TarFile` | `dict[str, list[TarInfo]]` |
| `_open_zip_from_tar_members(tar, members, work_dir)` | zip 조각을 ZipFile로 오픈 (조각 1개면 디스크 복사 없이 스트림으로, 여러 개면 임시 파일로 병합) | `tar, members, work_dir` | context manager, `ZipFile` |
| `process_ts_tar(tar_path, class_table, processed_images_dir)` | zip 중앙 디렉터리만 읽어 유효 category_id 이미지만 선택적으로 압축 해제 | `tar_path, class_table, processed_images_dir` | `(matched_category_ids, file_counts)` |
| `_process_ts_tar_with_retry(...)` | `process_ts_tar`를 최대 3회 재시도하며 실행 | `tar_path, class_table, processed_images_dir, max_attempts` | `(matched_category_ids, file_counts)` |
| `verify_extracted_images(processed_images_dir, file_counts)` | 방금 옮긴 개수가 실제 디스크 파일 수와 일치하는지 검증 | `processed_images_dir, file_counts` | `bool` |
| `load_state(path)` / `save_state(state, path)` | `_image_state.json` 체크포인트 로드/저장 | `path` / `state, path` | `dict` / - |
| `write_image_count_md/csv(...)` | 클래스별 이미지 개수를 md/csv로 기록 | `class_table, total_file_counts, path` | - |
| `main()` | 미완료 `TS_*` tar만 순서대로 처리 → 검증 → 원본 삭제까지 수행하는 진입점 | - | - |

---

## shared_dataset_composer.py

`data/raw/train_images` + `train_annotations`를 YOLO 학습 포맷으로 변환해
`data/processed/shared`에 train/val로 나눠 저장합니다. **다른 스크립트와 달리 `main()`으로
감싸여 있지 않고 모듈 최상위에서 바로 실행되는 스크립트**이며, 배경(negative) 이미지 추가를 위해
`background_extractor.py`를 모듈로 import해서 그 함수들을 재사용합니다.

Train/Val 분리는 이미지 단위가 아니라 **데이터(K-코드) 단위**로 이루어집니다. 파일명 앞부분의
K-코드(예: `K-000250-000573-..._0_0.png` → `K-000250-000573`)가 같으면 각도만 다른 동일한
물리적 알약 배치이므로, 이게 train/val 양쪽에 걸치면 사실상 같은 사진을 양쪽에서 채점하는
데이터 누수가 됩니다. 이를 원천 차단하기 위해 같은 K-코드는 항상 train/val 중 한쪽에만 배정하고,
그 상태에서 데이터 수가 적은 클래스부터 우선 배정해 클래스 균형도 함께 맞춥니다. 마지막으로
train에 아예 없는 클래스가 남으면 val → train으로 자동 보정합니다.

또한 train 변환이 끝난 뒤, 데이터 수가 적은 클래스는 이미지를 복제해 최소 확보 수량
(`OVERSAMPLE_TARGET_MIN_COUNT`, 기본 20장)을 채우는 Oversampling까지 자동으로 이어서 실행합니다.

### 필요한 디렉토리 구조 (입력)

```
data/raw/
├── train_images/
│   └── *.png                      # collect_dataset_merger.py / collect_single_* 로 채워진 최종 이미지
└── train_annotations/
    └── **/*.json                  # images[0]{file_name,width,height}, annotations[].{bbox,category_id}, categories[].{id,name}
```

### 만들어지는 결과물 (출력)

```
data/processed/shared/
├── images/
│   ├── train/*.png                # 원본 알약 이미지 + 배경(negative) 이미지 + Oversampling 복제본(*_dupN.png) 포함
│   └── val/*.png
├── labels/
│   ├── train/*.txt                # YOLO 포맷(class cx cy w h, 정규화됨). 배경 이미지는 빈 txt
│   └── val/*.txt
├── class_mapping.json             # {원본 category_id: YOLO 클래스 인덱스}
├── classes.txt                    # YOLO 클래스 인덱스 순서의 class name 목록
└── dataset.yaml                   # YOLO 학습용 데이터셋 설정 파일 (path/train/val/names)
```

추가로 `background_extractor.py`의 `OUTPUT`(`data/processed/backgrounds`)에도 배경 이미지를
새로 생성해 저장합니다(이미 있으면 덮어씀).

### 주요 로직 / 함수

| 대상 | 설명 | 인자 | 반환값 |
|---|---|---|---|
| (모듈 최상위) | 모든 라벨 json을 읽어 `category_dict`(id→name), `class_map`(id→YOLO index), `image_meta`(파일명→width/height/anns)를 구성하고 `class_mapping.json`/`classes.txt` 저장 | - | - |
| `get_combo_id(image_name)` | 파일명 앞부분(K-코드)을 데이터(콤보) ID로 추출 | `image_name: str` | `str` |
| `combo_stratified_split(image_meta, class_map, all_category_ids, train_ratio, seed)` | 데이터(K-코드) 단위로 묶어 train/val을 나눠 같은 물리적 알약 배치가 양쪽에 걸치는 데이터 누수를 방지. 데이터 수가 적은 클래스부터 우선 배정하고, train에 없는 클래스는 val → train으로 자동 보정 | `image_meta, class_map, all_category_ids, train_ratio, seed` | `(train_images, val_images)` |
| `find_image(image_name)` | `IMAGE_ROOT`에서 이미지 파일을 찾음 (없으면 하위 전체 검색) | `image_name: str` | `Path \| None` |
| `convert(image_names, mode)` | 이미지별 통합 어노테이션을 YOLO txt로 변환하고 이미지를 `images/<mode>`로 복사 | `image_names, mode` | - |
| `add_background_images(output_dir, num_backgrounds, seed)` | `background_extractor`로 배경 이미지를 만들어 train에만 negative 샘플로 추가 | `output_dir, num_backgrounds, seed` | - |
| `oversample_rare_classes(output_dir, target_min_count, class_names)` | train에서 `target_min_count`장 미만인, 데이터 수가 적은 클래스를 이미지 복제(`_dupN` 접미사)로 채움 | `output_dir, target_min_count, class_names` | - |
| (모듈 최상위) | `convert(train, "train")` → `convert(val, "val")` → `add_background_images(...)` → `oversample_rare_classes(...)` → `dataset.yaml` 작성 순으로 실행 | - | - |
