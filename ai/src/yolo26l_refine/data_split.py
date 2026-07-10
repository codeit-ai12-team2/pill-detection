# ============================================================
# 파일 역할: data_split.py
# 학습 전 데이터 준비 단계. 아래 4가지를 CLI 명령으로 실행:
#   1) check      - train/val에 같은 알약(K-코드)이 섞여 있는지 점검
#   2) resplit     - 56개 클래스가 train/val 양쪽에 다 있도록 재분리
#   3) oversample  - 개수가 적은 클래스를 복제해서 채움
#   4) restore/cleanup - 재분리 이전 상태로 되돌리기 / v2 폴더 정리
# train.py를 돌리기 "전에" 한 번 실행해서 데이터 자체를 정리하는 파일.
# ============================================================
"""Train/Val 콤보(K-코드) 기반 데이터 누수 점검, 클래스 균형 재분리, 희귀 클래스 oversampling.

사용 예:
    python data_split.py check
    python data_split.py resplit               # 계획만 계산 (파일 이동 없음)
    python data_split.py resplit --apply        # 실제로 재배치까지 실행
    python data_split.py oversample --target-min-count 20
    python data_split.py restore                # 재분리 이전으로 복구
    python data_split.py cleanup                # 복구 후 남은 v2 폴더 완전 삭제 (되돌릴 수 없음)
"""

import argparse
import random
import shutil
from collections import defaultdict

from common import IMAGES_DIR, LABELS_DIR, load_class_names


def get_combo_id(filename: str) -> str:
    """파일명 앞부분의 K-코드 조합(콤보 ID)을 추출합니다.

    파일명 패턴: K-XXXXXX-XXXXXX-..._각도_....png
    """
    return filename.split("_")[0]


def check_leakage() -> None:
    """현재 train/val 사이에 겹치는 콤보(K-코드 조합)가 있는지 점검합니다."""
    train_dir = IMAGES_DIR / "train"
    val_dir = IMAGES_DIR / "val"

    train_combos = {get_combo_id(p.name) for p in train_dir.glob("*.png")}
    val_combos = {get_combo_id(p.name) for p in val_dir.glob("*.png")}
    overlap = train_combos & val_combos

    print(f"train 콤보 수: {len(train_combos)}")
    print(f"val 콤보 수: {len(val_combos)}")
    print(f"겹치는 콤보 수: {len(overlap)}")
    print(f"val 콤보 중 겹치는 비율: {len(overlap) / len(val_combos):.1%}")

    if overlap:
        print("\n⚠️ train/val에 같은 알약 조합이 섞여 있습니다. val 점수가 실제보다 높게 나올 수 있습니다.")
        print("예시 (최대 5개):", list(overlap)[:5])
    else:
        print("\n✅ train/val 콤보가 완전히 분리되어 있습니다. 데이터 누수 문제는 아닙니다.")


def _load_combo_maps():
    """전체 이미지에서 콤보별 파일 stem 목록과 콤보별 클래스 집합을 만듭니다."""
    class_names = load_class_names()
    all_files = list((IMAGES_DIR / "train").glob("*.png")) + list((IMAGES_DIR / "val").glob("*.png"))

    combo_to_files = defaultdict(list)
    combo_to_classes = defaultdict(set)

    for f in all_files:
        combo = get_combo_id(f.name)
        combo_to_files[combo].append(f.stem)

        label_path = LABELS_DIR / "train" / f"{f.stem}.txt"
        if not label_path.exists():
            label_path = LABELS_DIR / "val" / f"{f.stem}.txt"
        with open(label_path, encoding="utf-8") as lf:
            for line in lf:
                combo_to_classes[combo].add(int(line.split()[0]))

    return class_names, combo_to_files, combo_to_classes


def plan_resplit(val_ratio: float = 0.2, seed: int = 42):
    """56개 클래스 전부가 train/val 양쪽에 최소 1개씩 들어가도록 콤보를 재배정합니다.

    희귀 클래스(콤보 수가 적은 클래스)부터 우선 배정하고, 부족한 val 비율은
    남은 콤보로 채웁니다. 마지막에 train에서 완전히 빠진 클래스가 있으면
    val -> train으로 강제 편입해 자동 보정합니다.

    Args:
        val_ratio: 목표 val 비율.
        seed: 랜덤 시드.

    Returns:
        (combo_to_files, train_combos, val_combos) 튜플.
    """
    random.seed(seed)
    class_names, combo_to_files, combo_to_classes = _load_combo_maps()

    all_classes = set()
    for classes in combo_to_classes.values():
        all_classes |= classes
    print(f"전체 클래스 수: {len(all_classes)}")

    class_to_combos = defaultdict(set)
    for combo, classes in combo_to_classes.items():
        for c in classes:
            class_to_combos[c].add(combo)

    class_order = sorted(class_to_combos.keys(), key=lambda c: len(class_to_combos[c]))

    combos = list(combo_to_files.keys())
    val_combos = set()
    train_combos = set(combos)

    for cls_idx in class_order:
        combo_list = list(class_to_combos[cls_idx])
        random.shuffle(combo_list)

        has_in_val = any(c in val_combos for c in combo_list)
        has_in_train = any(c in train_combos for c in combo_list)

        if not has_in_val and combo_list:
            candidates = [c for c in combo_list if c in train_combos]
            if candidates:
                chosen = candidates[0]
                val_combos.add(chosen)
                train_combos.discard(chosen)

        if not has_in_train and combo_list:
            candidates = [c for c in combo_list if c in val_combos]
            if len(combo_list) > 1 and candidates:
                chosen = candidates[0]
                train_combos.add(chosen)
                val_combos.discard(chosen)

    n_val_target = int(len(combos) * val_ratio)
    remaining = [c for c in train_combos if c not in val_combos]
    random.shuffle(remaining)
    additional_needed = max(0, n_val_target - len(val_combos))
    for combo in remaining[:additional_needed]:
        val_combos.add(combo)
        train_combos.discard(combo)

    print(f"train 콤보 {len(train_combos)}개, val 콤보 {len(val_combos)}개")

    train_class_check = set()
    for combo in train_combos:
        train_class_check |= combo_to_classes[combo]
    val_class_check = set()
    for combo in val_combos:
        val_class_check |= combo_to_classes[combo]

    overlap = train_combos & val_combos
    print(f"train에 포함된 클래스: {len(train_class_check)} / {len(all_classes)}")
    print(f"val에 포함된 클래스: {len(val_class_check)} / {len(all_classes)}")
    print(f"train/val 콤보 중복: {len(overlap)}")

    missing_in_val = all_classes - val_class_check
    missing_in_train = all_classes - train_class_check
    if missing_in_val:
        print(f"⚠️ val에 여전히 없는 클래스: {[class_names[i] for i in missing_in_val]}")
    if missing_in_train:
        print(f"⚠️ train에 여전히 없는 클래스: {[class_names[i] for i in missing_in_train]}")
    if not missing_in_val and not missing_in_train and not overlap:
        print("✅ 모든 클래스가 train/val 양쪽에 존재하며, 콤보 중복 없음")

    # ===== train에 없는 클래스 자동 보정 (val -> train 강제 편입) =====
    train_class_check = set()
    for combo in train_combos:
        train_class_check |= combo_to_classes[combo]

    missing_in_train = all_classes - train_class_check
    if missing_in_train:
        print(f"\ntrain에 없는 클래스 {len(missing_in_train)}개 자동 보정 중...")
        for cls_idx in missing_in_train:
            combo_list = list(class_to_combos[cls_idx])
            chosen = combo_list[0]
            if chosen in val_combos:
                val_combos.discard(chosen)
                train_combos.add(chosen)
                print(f"  {class_names[cls_idx]}: 콤보를 val -> train으로 이동")

    # ===== 최종 재검증 =====
    train_class_check = set()
    for combo in train_combos:
        train_class_check |= combo_to_classes[combo]
    val_class_check = set()
    for combo in val_combos:
        val_class_check |= combo_to_classes[combo]
    overlap_final = train_combos & val_combos

    print(f"\n[최종] train 클래스: {len(train_class_check)} / {len(all_classes)}")
    print(f"[최종] val 클래스: {len(val_class_check)} / {len(all_classes)}")
    print(f"[최종] 콤보 중복: {len(overlap_final)}")

    still_missing_train = all_classes - train_class_check
    if still_missing_train:
        print(f"⚠️ 여전히 train에 없는 클래스 (콤보가 1개뿐이라 보정 불가): {[class_names[i] for i in still_missing_train]}")
    if not overlap_final and not still_missing_train:
        print(f"✅ train은 {len(all_classes)}개 클래스 전부 확보, 콤보 중복 없음 (val 일부 클래스 누락은 데이터 한계로 감수)")

    return combo_to_files, train_combos, val_combos


def apply_resplit(combo_to_files, train_combos, val_combos) -> None:
    """재분리 계획대로 실제 파일을 train_v2/val_v2에 복사한 뒤, 기존 폴더와 교체합니다.

    기존 train/val은 train_old/val_old로 보존되므로 restore()로 되돌릴 수 있습니다.
    """
    new_train_img = IMAGES_DIR / "train_v2"
    new_val_img = IMAGES_DIR / "val_v2"
    new_train_lbl = LABELS_DIR / "train_v2"
    new_val_lbl = LABELS_DIR / "val_v2"
    for d in [new_train_img, new_val_img, new_train_lbl, new_val_lbl]:
        d.mkdir(exist_ok=True)

    train_count, val_count = 0, 0
    for combo, stems in combo_to_files.items():
        target_img_dir = new_train_img if combo in train_combos else new_val_img
        target_lbl_dir = new_train_lbl if combo in train_combos else new_val_lbl

        for stem in stems:
            src_img = IMAGES_DIR / "train" / f"{stem}.png"
            if not src_img.exists():
                src_img = IMAGES_DIR / "val" / f"{stem}.png"
            src_lbl = LABELS_DIR / "train" / f"{stem}.txt"
            if not src_lbl.exists():
                src_lbl = LABELS_DIR / "val" / f"{stem}.txt"

            shutil.copy(src_img, target_img_dir / f"{stem}.png")
            shutil.copy(src_lbl, target_lbl_dir / f"{stem}.txt")

            if combo in train_combos:
                train_count += 1
            else:
                val_count += 1

    print(f"재배치 완료: train {train_count}장, val {val_count}장")

    shutil.move(IMAGES_DIR / "train", IMAGES_DIR / "train_old")
    shutil.move(IMAGES_DIR / "val", IMAGES_DIR / "val_old")
    shutil.move(LABELS_DIR / "train", LABELS_DIR / "train_old")
    shutil.move(LABELS_DIR / "val", LABELS_DIR / "val_old")

    shutil.move(new_train_img, IMAGES_DIR / "train")
    shutil.move(new_val_img, IMAGES_DIR / "val")
    shutil.move(new_train_lbl, LABELS_DIR / "train")
    shutil.move(new_val_lbl, LABELS_DIR / "val")

    print("교체 완료")


def oversample_rare_classes(target_min_count: int = 20) -> None:
    """train에서 target_min_count장 미만인 클래스를 복제해서 채웁니다.

    재분리된 train 폴더 기준으로 동작하므로, resplit을 먼저 적용한 뒤 실행하세요.

    Args:
        target_min_count: 클래스당 최소 확보할 이미지 수.
    """
    class_names = load_class_names()

    class_counts = {}
    for label_path in (LABELS_DIR / "train").glob("*.txt"):
        with open(label_path, encoding="utf-8") as f:
            for line in f:
                cls_idx = int(line.split()[0])
                class_counts[cls_idx] = class_counts.get(cls_idx, 0) + 1

    low_classes = [idx for idx, count in class_counts.items() if count < target_min_count]
    print(f"oversampling 대상 클래스 {len(low_classes)}개")

    for target_idx in low_classes:
        class_name = class_names[target_idx]
        matched = []
        for label_path in (LABELS_DIR / "train").glob("*.txt"):
            with open(label_path, encoding="utf-8") as f:
                has_class = any(int(line.split()[0]) == target_idx for line in f)
            if has_class:
                matched.append(label_path.stem)

        current_count = len(matched)
        copies_needed = max(0, target_min_count - current_count)
        print(f"{class_name}: 현재 {current_count}개 -> {copies_needed}개 복제")

        for i in range(copies_needed):
            src_stem = matched[i % current_count]
            new_stem = f"{src_stem}_dup{i}"

            shutil.copy(IMAGES_DIR / "train" / f"{src_stem}.png", IMAGES_DIR / "train" / f"{new_stem}.png")
            shutil.copy(LABELS_DIR / "train" / f"{src_stem}.txt", LABELS_DIR / "train" / f"{new_stem}.txt")

    print("oversampling 완료")


def restore_original() -> None:
    """재분리 이전(train_old/val_old) 상태로 복구합니다. resplit --apply를 한 번이라도 실행한 경우에만 동작합니다."""
    if (IMAGES_DIR / "train").exists():
        shutil.move(IMAGES_DIR / "train", IMAGES_DIR / "train_v2")
    if (IMAGES_DIR / "val").exists():
        shutil.move(IMAGES_DIR / "val", IMAGES_DIR / "val_v2")
    if (LABELS_DIR / "train").exists():
        shutil.move(LABELS_DIR / "train", LABELS_DIR / "train_v2")
    if (LABELS_DIR / "val").exists():
        shutil.move(LABELS_DIR / "val", LABELS_DIR / "val_v2")

    shutil.move(IMAGES_DIR / "train_old", IMAGES_DIR / "train")
    shutil.move(IMAGES_DIR / "val_old", IMAGES_DIR / "val")
    shutil.move(LABELS_DIR / "train_old", LABELS_DIR / "train")
    shutil.move(LABELS_DIR / "val_old", LABELS_DIR / "val")

    (LABELS_DIR / "train.cache").unlink(missing_ok=True)
    (LABELS_DIR / "val.cache").unlink(missing_ok=True)

    print("원본 상태로 복구 완료")


def cleanup_v2() -> None:
    """복구 후 남은 train_v2/val_v2를 완전히 삭제합니다. 되돌릴 수 없으니 신중하게 실행하세요."""
    shutil.rmtree(IMAGES_DIR / "train_v2", ignore_errors=True)
    shutil.rmtree(IMAGES_DIR / "val_v2", ignore_errors=True)
    shutil.rmtree(LABELS_DIR / "train_v2", ignore_errors=True)
    shutil.rmtree(LABELS_DIR / "val_v2", ignore_errors=True)
    print("v2 폴더 완전 삭제 완료")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train/Val 콤보 기반 데이터 누수 점검 및 재분리")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="train/val 콤보 중복 여부만 점검합니다.")

    resplit_parser = sub.add_parser("resplit", help="클래스 균형을 보장하며 train/val을 재분리합니다.")
    resplit_parser.add_argument("--val-ratio", type=float, default=0.2)
    resplit_parser.add_argument("--seed", type=int, default=42)
    resplit_parser.add_argument("--apply", action="store_true", help="계획만 보지 않고 실제로 파일을 재배치합니다.")

    oversample_parser = sub.add_parser("oversample", help="희귀 클래스를 복제해 최소 개수를 채웁니다.")
    oversample_parser.add_argument("--target-min-count", type=int, default=20)

    sub.add_parser("restore", help="재분리 이전 상태로 복구합니다.")
    sub.add_parser("cleanup", help="복구 후 남은 v2 폴더를 완전히 삭제합니다 (되돌릴 수 없음).")

    args = parser.parse_args()

    if args.command == "check":
        check_leakage()
    elif args.command == "resplit":
        combo_to_files, train_combos, val_combos = plan_resplit(val_ratio=args.val_ratio, seed=args.seed)
        if args.apply:
            apply_resplit(combo_to_files, train_combos, val_combos)
        else:
            print("\n계획만 계산했습니다. 실제로 파일을 옮기려면 --apply 옵션을 추가하세요.")
    elif args.command == "oversample":
        oversample_rare_classes(target_min_count=args.target_min_count)
    elif args.command == "restore":
        restore_original()
    elif args.command == "cleanup":
        cleanup_v2()


if __name__ == "__main__":
    main()
