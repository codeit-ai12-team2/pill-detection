import json
from pathlib import Path

import pandas as pd
import torch
import yaml
from ultralytics import YOLO
from tqdm import tqdm

YOLO_DIR = Path(__file__).parent


def load_config(config_path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_device() -> int | str:
    if torch.cuda.is_available():
        print("CUDA is available. Using GPU.")
        return 0
    if torch.backends.mps.is_available():
        print("MPS is available. Using MPS.")
        return "mps"
    print("CUDA or MPS is not available. Using CPU.")
    return "cpu"


def find_best_weights(model_name: str) -> Path | None:
    """선택된 모델의 가장 최근 학습 결과에서 best.pt 경로를 반환합니다."""
    runs_dir = YOLO_DIR / "runs/detect"
    if not runs_dir.exists():
        return None
    candidates = sorted(
        [d for d in runs_dir.glob(f"{model_name}*") if (d / "weights/best.pt").exists()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return (candidates[0] / "weights/best.pt") if candidates else None


def main(model_name: str = "yolo11s"):
    device = get_device()

    config = load_config(YOLO_DIR / "interface.yaml")

    best_pt = find_best_weights(model_name)
    if best_pt is None:
        print(f"[오류] '{model_name}'의 학습된 가중치(best.pt)를 찾을 수 없습니다.")
        print("먼저 학습(train)을 실행하세요.")
        return

    print(f"사용할 가중치: {best_pt}")

    test_dir = (YOLO_DIR / config["test_dir"]).resolve()
    class_mapping_file = (YOLO_DIR / config["class_mapping_file"]).resolve()
    output_dir = (YOLO_DIR / f"../../outputs/{model_name}").resolve()

    output_file_path = output_dir / "submission.csv"
    output_file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(class_mapping_file, encoding="utf-8") as f:
        class_map = json.load(f)

    reversed_map = {int(v): int(k) for k, v in class_map.items()}

    model = YOLO(best_pt)
    rows = []
    annotation_id = 1

    for image_path in tqdm(sorted(test_dir.glob("*"), key=lambda p: int(p.stem)), desc="predict\t"):
        image_id = int(image_path.stem)

        results = model.predict(
            source=image_path,
            imgsz=config["imgsz"],
            conf=config["conf"],
            iou=config["iou"],
            device=device,
            verbose=False,
        )

        for box in results[0].boxes:
            cls = int(box.cls.item())
            score = float(box.conf.item())
            x1, y1, x2, y2 = box.xyxy[0].tolist()

            rows.append({
                "annotation_id": annotation_id,
                "image_id": image_id,
                "category_id": reversed_map[cls],
                "bbox_x": round(x1),
                "bbox_y": round(y1),
                "bbox_w": round(x2 - x1),
                "bbox_h": round(y2 - y1),
                "score": score,
            })
            annotation_id += 1

    df = pd.DataFrame(rows)
    df.to_csv(output_file_path, index=False)
    print(f"결과 저장 완료: {output_file_path}")


if __name__ == "__main__":
    main()