from pathlib import Path

import yaml
from ultralytics import YOLO

YOLO_DIR = Path(__file__).parent


def load_config(config_path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_best_weights(model_name: str) -> Path | None:
    """선택된 모델의 가장 최근 학습 결과에서 best.pt 경로를 반환합니다."""
    runs_dir = YOLO_DIR / "runs/detect"
    if not runs_dir.exists():
        return None
    candidates = sorted(
        [
            d
            for d in runs_dir.glob(f"{model_name}*")
            if (d / "weights/best.pt").exists()
        ],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return (candidates[0] / "weights/best.pt") if candidates else None


def convert_to_coreml(weights_path: Path, imgsz: int) -> Path:
    """weights_path 의 pt 모델을 CoreML로 변환합니다.

    ultralytics 의 export() 는 결과물을 원본 가중치와 같은 폴더에 저장하므로
    (예: runs/detect/yolo26l/weights/best.pt -> best.mlpackage), 별도로
    저장 경로를 옮기지 않습니다.

    Args:
        weights_path: 변환할 .pt 가중치 경로.
        imgsz: 변환 시 사용할 입력 이미지 크기.

    Returns:
        생성된 .mlpackage 경로.
    """
    model = YOLO(weights_path)
    exported_path = model.export(format="coreml", imgsz=imgsz, nms=True)
    return Path(exported_path)


def main(model_name: str = "yolo26l"):
    config = load_config(YOLO_DIR / "interface.yaml")

    best_pt = find_best_weights(model_name)
    if best_pt is None:
        print(f"[오류] '{model_name}'의 학습된 가중치(best.pt)를 찾을 수 없습니다.")
        print("먼저 학습(train)을 실행하세요.")
        return

    print(f"변환할 가중치: {best_pt}")

    exported_path = convert_to_coreml(best_pt, config["imgsz"])

    print(f"CoreML 변환 완료: {exported_path}")


if __name__ == "__main__":
    main()
