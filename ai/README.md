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
┃ ┣ 📂 yolo11s
┃ ┣ 📂 yolo26l
┃ ┣ 📂 yolo26l-17
┃ ┣ 📂 yolo26l-21
┃ ┗ 📂 yolo26s
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

## 4. 데이터 처리

원본 데이터를 학습에 쓸 수 있는 형태로 가공하는 스크립트와 파이프라인은 아래 문서를 참고하세요.

- 📎 [ai/src/util README](src/util/README.md)

### init.py 실행 방법

```
cd ai/src
python init.py
```

실행하면 아래 순서로 메뉴가 나타납니다.

1. 동작 선택: 학습(train) / 예측(predict) / 성능 확인(result) / CoreML 변환(convert)
2. 모델 선택: `src/yolo` 디렉토리의 모델 설정(yaml) 목록 중 선택
3. (학습·예측인 경우) 데이터셋 버전 선택: 본 문서에서는 `v1 (data/processed/shared)` 기준으로 진행합니다.

이후 선택한 동작에 따라 `train.py` / `test.py` / `result.py` / `model_converter.py`가 실행됩니다.

## 5. 최종 모델 (YOLO)
