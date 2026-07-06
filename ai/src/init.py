"""알약 탐지 시스템 CLI 진입점.

터미널에서 실행:
    python init.py
"""

import sys
from pathlib import Path

import yaml

YOLO_DIR = Path(__file__).parent / "yolo"
sys.path.insert(0, str(YOLO_DIR))


def load_model_configs() -> list[dict]:
    """yolo 디렉터리에서 모델 설정 파일(name + model 키만 있는 yaml)을 검색합니다."""
    configs = []
    for yaml_path in sorted(YOLO_DIR.glob("*.yaml")):
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if set(data.keys()) == {"model", "name"}:
            configs.append({"stem": yaml_path.stem, "name": data["name"]})
    return configs


def choose(options: list[str], prompt: str) -> int:
    """번호 메뉴를 출력하고 선택된 0-based 인덱스를 반환합니다."""
    print(f"\n[{prompt}]")
    for i, opt in enumerate(options, 1):
        print(f"  {i}. {opt}")
    while True:
        raw = input("> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw) - 1
        print(f"  1 ~ {len(options)} 사이의 숫자를 입력하세요.")


def main():
    print("\n=== 알약 탐지 시스템 ===")

    model_configs = load_model_configs()
    if not model_configs:
        print("[오류] 사용 가능한 모델 설정 파일이 없습니다.")
        print(f"       {YOLO_DIR} 에 {{name, model}} 키를 가진 yaml 파일을 추가하세요.")
        sys.exit(1)

    action_idx = choose(["학습 (train)", "예측 (predict)", "성능 확인 (result)"], "동작 선택")

    print()

    if action_idx == 2:
        # 성능 확인은 전체 모델을 한 번에 비교할지, 특정 모델만 볼지 선택
        scope_idx = choose(["전체 모델 비교", "특정 모델만 확인"], "확인 범위 선택")
        from result import main as result_main

        if scope_idx == 0:
            print("[전체 모델 성능 비교]")
            result_main(model_name=None)
        else:
            model_idx = choose([cfg["name"] for cfg in model_configs], "모델 선택")
            selected = model_configs[model_idx]
            print(f"[{selected['name']} 성능 확인]")
            result_main(model_name=selected["stem"])
        return

    model_idx = choose([cfg["name"] for cfg in model_configs], "모델 선택")
    selected = model_configs[model_idx]

    if action_idx == 0:
        from train import main as train_main
        print(f"[{selected['name']} 학습 시작]")
        train_main(model_name=selected["stem"])
    else:
        from test import main as test_main
        print(f"[{selected['name']} 예측 시작]")
        test_main(model_name=selected["stem"])


if __name__ == "__main__":
    main()