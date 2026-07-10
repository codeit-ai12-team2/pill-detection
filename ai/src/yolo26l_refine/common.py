"""yolo 트랙 공통 경로 상수와 설정/디바이스 관련 유틸리티.

모든 스크립트(data_split.py, train.py, evaluate.py, hard_negative.py, predict.py)가
이 모듈에서 경로와 공통 함수를 가져와 씁니다. 경로는 이 파일의 위치(ai/src/yolo/)를
기준으로 계산하므로, 저장소를 어디에 clone하든 그대로 동작합니다.
"""

from pathlib import Path

import torch
import yaml

YOLO_DIR = Path(__file__).resolve().parent
AI_DIR = YOLO_DIR.parents[1]

DATA_DIR = AI_DIR / "data" / "processed" / "shared"
IMAGES_DIR = DATA_DIR / "images"
LABELS_DIR = DATA_DIR / "labels"
CLASSES_FILE = DATA_DIR / "classes.txt"
CLASS_MAPPING_FILE = DATA_DIR / "class_mapping.json"
DATASET_YAML = DATA_DIR / "dataset.yaml"

OUTPUT_DIR = AI_DIR / "outputs" / "yolo"
RUNS_DIR = OUTPUT_DIR / "runs" / "detect"


def load_config(config_path) -> dict:
    """YAML 설정 파일을 읽어 dict로 반환합니다.

    Args:
        config_path: 읽을 yaml 파일 경로.
    """
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_class_names() -> list:
    """classes.txt에서 클래스 이름 목록을 순서대로 읽어옵니다."""
    with open(CLASSES_FILE, encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def get_device() -> int | str:
    """사용 가능한 학습/추론 디바이스를 반환합니다 (CUDA > MPS > CPU 순)."""
    if torch.cuda.is_available():
        print("CUDA is available. Using GPU.")
        return 0
    if torch.backends.mps.is_available():
        print("MPS is available. Using MPS.")
        return "mps"
    print("CUDA or MPS is not available. Using CPU.")
    return "cpu"


def find_latest_run(model_name: str) -> Path:
    """outputs/yolo/runs/detect 아래에서 model_name으로 시작하는 가장 최근 학습 폴더를 찾습니다.

    Args:
        model_name: 예) "yolo26l", "yolo26l_hardneg"
    """
    candidates = [
        d for d in RUNS_DIR.glob(f"{model_name}*") if (d / "weights/best.pt").exists()
    ]
    if not candidates:
        raise FileNotFoundError(
            f"{model_name} 학습 결과를 찾을 수 없습니다. 먼저 학습을 실행하세요."
        )
    return max(candidates, key=lambda d: d.stat().st_mtime)


def find_latest_weights() -> Path:
    """outputs/yolo/runs/detect 전체에서 가장 최근에 학습된 best.pt를 찾습니다."""
    candidates = list(RUNS_DIR.glob("*/weights/best.pt"))
    if not candidates:
        raise FileNotFoundError("학습된 best.pt가 없습니다. 먼저 학습을 실행하세요.")
    return max(candidates, key=lambda p: p.stat().st_mtime)
