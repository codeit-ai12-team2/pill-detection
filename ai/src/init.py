"""알약 탐지 시스템 CLI 진입점.

터미널에서 실행:
    python init.py
"""

import sys
from pathlib import Path

import yaml

sys.stdin.reconfigure(encoding="utf-8", errors="replace")

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


def choose_dataset_version() -> str:
    """데이터셋 버전(v1/v2) 선택 메뉴를 출력하고 선택값을 반환합니다."""
    dataset_idx = choose(
        ["v1 (data/processed/shared)", "v2 (data/processed/shared_v2)"],
        "데이터셋 버전 선택",
    )
    return "v1" if dataset_idx == 0 else "v2"


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


def choose_model(model_configs: list[dict]) -> dict:
    """모델 선택 메뉴를 출력하고 선택된 모델 설정을 반환합니다."""
    model_idx = choose([cfg["name"] for cfg in model_configs], "모델 선택")
    return model_configs[model_idx]


def prompt_hardneg_classes() -> list[str] | None:
    """Hard Negative Mining을 학습 마지막 단계로 이어서 실행할지 묻고, 대상 클래스 목록을 반환합니다."""
    apply_idx = choose(
        ["아니오 (학습만 진행)", "예 (학습 직후 이어서 진행)"],
        "Hard Negative Mining도 이어서 진행할까요?",
    )
    if apply_idx == 0:
        return None
    raw = input("헷갈리는 클래스명을 쉼표(,)로 구분해 입력하세요: ").strip()
    target_class_names = [name.strip() for name in raw.split(",") if name.strip()]
    if not target_class_names:
        print("[안내] 클래스명이 입력되지 않아 Hard Negative Mining은 생략합니다.")
        return None
    return target_class_names


def run_result_analysis(selected: dict, dataset_version_choice) -> None:
    """특정 모델의 성능 확인 메뉴(기본 지표 / Confusion Matrix / Grid Search / 클래스별 성능)를 실행합니다."""
    from result import (
        DATASET_PATHS,
        class_scores_below,
        find_best_weights,
        grid_search_thresholds,
        plot_normalized_confusion_matrix,
        save_interface_config,
    )
    from result import (
        YOLO_DIR as RESULT_YOLO_DIR,
    )
    from result import (
        main as result_main,
    )

    analysis_idx = choose(
        [
            "기본 지표 (mAP50 / mAP50-95 / recall)",
            "Confusion Matrix",
            "Threshold Grid Search",
            "클래스별 성능 (class-scores)",
        ],
        "성능 확인 방식 선택",
    )

    if analysis_idx == 0:
        print(f"[{selected['name']} 성능 확인]")
        result_main(model_name=selected["stem"])
        return

    dataset_version = dataset_version_choice()
    data_yaml = (RESULT_YOLO_DIR / DATASET_PATHS[dataset_version]).resolve()

    best_pt = find_best_weights(selected["stem"])
    if best_pt is None:
        print(
            f"[오류] '{selected['stem']}'의 학습된 가중치(best.pt)를 찾을 수 없습니다."
        )
        print("먼저 학습(train)을 실행하세요.")
        return

    if analysis_idx == 1:
        print(f"[{selected['name']} Confusion Matrix 확인]")
        plot_normalized_confusion_matrix(best_pt, data_yaml)
    elif analysis_idx == 2:
        save_idx = choose(
            ["결과만 확인", "최적 조합을 interface.yaml에 저장"],
            "그리드서치 결과 저장 여부",
        )
        print(f"[{selected['name']} Threshold Grid Search]")
        grid_df = grid_search_thresholds(best_pt, data_yaml)
        if save_idx == 1:
            best_row = grid_df.iloc[0]
            save_interface_config(
                conf=float(best_row["conf"]), iou=float(best_row["iou"])
            )
    else:
        conf_raw = input("확인할 conf 값을 입력하세요 (예: 0.15): ").strip()
        iou_raw = input("확인할 iou 값을 입력하세요 (예: 0.5): ").strip()
        conf = float(conf_raw) if conf_raw else 0.15
        iou = float(iou_raw) if iou_raw else 0.5
        print(f"[{selected['name']} 클래스별 성능 확인, conf={conf}, iou={iou}]")
        class_scores_below(best_pt, data_yaml, conf=conf, iou=iou)


def main():
    print("\n=== 알약 탐지 시스템 ===")

    model_configs = load_model_configs()
    if not model_configs:
        print("[오류] 사용 가능한 모델 설정 파일이 없습니다.")
        print(f"       {YOLO_DIR} 에 {{name, model}} 키를 가진 yaml 파일을 추가하세요.")
        sys.exit(1)

    action_idx = choose(
        [
            "학습 (train)",
            "예측 (predict)",
            "성능 확인 (result)",
            "CoreML 변환 (convert, macOS 혹은 Linux에서만 동작)",
        ],
        "동작 선택",
    )

    print()

    if action_idx == 2:
        # 성능 확인은 전체 모델을 한 번에 비교할지, 특정 모델만 볼지 선택
        scope_idx = choose(["전체 모델 비교", "특정 모델만 확인"], "확인 범위 선택")
        from result import main as result_main

        if scope_idx == 0:
            print("[전체 모델 성능 비교]")
            result_main(model_name=None)
        else:
            selected = choose_model(model_configs)
            run_result_analysis(selected, choose_dataset_version)
        return

    selected = choose_model(model_configs)

    if action_idx == 0:
        from train import main as train_main

        dataset_version = choose_dataset_version()
        hardneg_classes = prompt_hardneg_classes()
        print(f"[{selected['name']} 학습 시작, 데이터셋 {dataset_version}]")
        train_main(
            model_name=selected["stem"],
            dataset_version=dataset_version,
            hardneg_classes=hardneg_classes,
        )
    elif action_idx == 1:
        from test import main as test_main

        dataset_version = choose_dataset_version()
        print(f"[{selected['name']} 예측 시작, 데이터셋 {dataset_version}]")
        test_main(model_name=selected["stem"], dataset_version=dataset_version)
    else:
        from model_converter import main as convert_main

        print(f"[{selected['name']} CoreML 변환 시작]")
        convert_main(model_name=selected["stem"])


if __name__ == "__main__":
    main()
