# AI 통합 문서

## 1. 프로젝트 개요

알약 이미지에서 **클래스** 와 **바운딩 박스** 를 검출하는 Object Detection 모델을 개발하는
디렉토리입니다. 원본 데이터 수집·가공(`src/util`)부터 EDA, 모델 학습/예측/성능 평가/변환까지의
전체 파이프라인을 포함합니다.

## 2. Project Structure

```
📦 ai
┣ 📂 data
┃ ┣ 📂 collect            # 조합 알약(combo) 원본 다운로드
┃ ┣ 📂 collect_single     # 단일 알약 원본 다운로드
┃ ┣ 📂 processed          # YOLO 학습 포맷으로 변환된 데이터셋 (v1/v2)
┃ ┣ 📂 raw                # 정제된 원본 이미지/어노테이션 (v1)
┃ ┗ 📂 raw_v2             # 정제된 원본 이미지/어노테이션 (v2)
┣ 📂 notebooks            # EDA, 환경 점검 등 노트북
┣ 📂 outputs              # 모델별 추론 결과(submission.csv)
┣ 📂 src
┃ ┣ 📂 rt_detr            # RT-DETR 모델 학습/예측
┃ ┣ 📂 util               # 원본 데이터 수집·가공 스크립트
┃ ┃ ┗ 📂 v2
┃ ┣ 📂 visual             # 데이터셋/예측 결과 시각화
┃ ┣ 📂 yolo               # YOLO 모델 학습/예측/평가/변환
┃ ┣ 📝 dataset.py
┃ ┗ 📝 init.py            # 학습/예측/평가/변환 CLI 진입점
┣ 📃 README.md
┣ 📃 requirements.txt
┗ 📃 requirements_for_runpod.txt
```

📁 [데이터 다운로드 링크 (Google Drive)](https://drive.google.com/drive/folders/1W_8iUqnBash06zLwfmGdE7Ry3S40HfRS?usp=sharing)

## 3. EDA 분석 문서

#### **분석 목적**

- 학습 데이터의 품질을 사전에 검증하여 전처리 방향을 결정하기 위한 탐색적 데이터 분석 수행

#### **데이터 기본 정보**

| 항목 | 값 |
| --- | --- |
| 데이터셋 | AI12 경구약제 이미지 객체 검출 |
| 이미지 크기 | 976 x 1280 |
| 라벨 형식 | COCO 형식 |
| 전체 JSON 파일 수 | 763개 |
| 전체 클래스 수 | 56개 |
| 전체 라벨 수  | 763개 |

#### **분석 결과**

1. bbox 범위 초과 확인

| 항목 | 결과 |
| --- | --- |
| 범위 초과 건수 | 1개 |
| 처리 방향 | 범위 조정 필요 |

2. 클래스 분포 확인

| 항목 | 결과 |
| --- | --- |
| 전체 클래스 수 | 56개 |
| 전체 라벨 수  | 763개 |

[ 상위 10개 클래스 ]
- category_id=3351 (일양하이트린정 2mg): 153개
- category_id=3483 (기넥신에프정(은행엽엑스)(수출용)): 45개
- category_id=35206 (아토젯정 10/40mg): 37개
- category_id=16262 (크레스토정 20mg): 23개
- category_id=21325 (아토르바정 10mg): 22개
- category_id=16232 (리피토정 20mg): 21개
- category_id=3832 (뉴로메드정(옥시라세탐)): 20개
- category_id=20238 (플라빅스정 75mg): 20개
- category_id=36637 (로수젯정10/5밀리그램): 19개
- category_id=16548 (가바토파정 100mg): 18개

3. 작은 bbox 확인

| 항목 | 결과 |
| --- | --- |
| 기준 | 32px 미만 |
| 해당 건수 | 0개 |
| 처리 방향 | 불필요 |

#### **발견한 문제점**

| 문제 | 건수 | 처리 방향 |
| --- | --- | --- |
| bbox 범위 초과 | 1개 | 이미지 경계로 범위 조정 |
| 작은 bbox | 0개 | 해당 없음 |

## 4. 데이터 처리 및 모델 학습 (YOLO)

원본 데이터를 학습에 쓸 수 있는 형태로 가공하는 스크립트와 파이프라인은 아래 문서를 참고하세요.

- 📎 [ai/src/util README](src/util/README.md)

Kaggle 알약 탐지 데이터셋 + AI-Hub 데이터(TL/TS 조합 1, 3, 4, 5, 6, 7, 8)로 **YOLO26l** 모델을 학습합니다. 기본 파이프라인(데이터 가공 → 학습 → 평가 → 제출)에 더해, Kaggle 점수 개선을 위한 데이터 분리 · Oversampling · Hard Negative Mining · Threshold Grid Search를 함께 적용했습니다.

구현 프레임워크: `Ultralytics` (학습/추론/평가), `Albumentations` (커스텀 증강)

### 4-1. init.py 실행 방법

```
cd ai/src
python init.py
```

실행하면 아래 순서로 메뉴가 나타납니다.

1. 동작 선택: 학습(train) / 예측(predict) / 성능 확인(result) / CoreML 변환(convert)
2. 모델 선택: `src/yolo` 디렉토리의 모델 설정(yaml) 목록 중 선택
3. (학습·예측인 경우) 데이터셋 버전 선택: 본 문서에서는 `v1 (data/processed/shared)` 기준으로 진행합니다.

이후 선택한 동작에 따라 `train.py` / `test.py` / `result.py` / `model_converter.py`가 실행됩니다.

### 4-2. 하이퍼파라미터

```yaml
epochs: 100
batch: 16
seed: 42
optimizer: auto
cos_lr: false
```

### 4-3. 증강

YOLO 기본 증강(모자이크, 믹스업, hsv, 회전 등)은 대부분 0으로 꺼두고, `Albumentations`로 알약 특성에 맞춘 증강을 별도로 구성했습니다.

```yaml
imgsz: 640
mosaic: 0
mixup: 0
copy_paste: 0
hsv_h: 0
degrees: 0
flipud: 0
perspective: 0
```

- 회전(Rotate), 좌우반전(HorizontalFlip), 이동/스케일(Affine)
- 명암 대비(RandomBrightnessContrast), 노이즈(GaussNoise, ISONoise), 블러(MotionBlur, GaussianBlur)
- 대비 강화(CLAHE), 그림자(RandomShadow), 부분 가림(CoarseDropout), 압축 손상(ImageCompression)

### 4-4. 성능 개선 기법

| 기법 | 설명 |
| --- | --- |
| **Train/Val 데이터 기반 분리** | 같은 K-코드(알약 조합)가 train/val 양쪽에 겹치지 않도록 `shared_dataset_composer.py`가 처음부터 데이터 단위로 분리. 데이터 수가 적은 클래스부터 우선 배정해 56개 클래스 전부가 train에 최소 1개 이상 포함되도록 함 |
| **Oversampling** | Train 기준 데이터가 일정 개수 미만인 클래스를 복제하여 최소 확보 수량을 채움 |
| **Threshold Grid Search** | conf(0.05-0.3) · iou(0.4-0.7) 조합을 그리드서치하여 mAP50-95 기준 최적 threshold를 탐색하고 `interface.yaml`에 반영 |

### 4-5. CoreML 변환 (iOS 연동)

```bash
python model_converter.py
```

`runs/detect/{model_name}*/weights/best.pt`를 CoreML(`.mlpackage`)로 변환합니다. 변환된 파일은 `Pillaw/App/Resources/yolo.mlpackage` 경로로 옮겨야 iOS 앱에서 인식합니다.

