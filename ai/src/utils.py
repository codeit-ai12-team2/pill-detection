import os
import json
from pathlib import Path
import torch
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from PIL import Image

def load_sample_from_json(annot_folder_path: str, image_dir: str) -> tuple:
    """
    annotations 폴더에서 해당 이미지 및 바운딩 박스 정도 다운

    Args:
        annot_folder_path (str): annotations 폴더 경로
        image_dir (str): 이미지 파일 폴더 경로

    Returns:
        tuple: (image, target)
            - image (PIL.Image): RGB
            - target(dict): {
                "boxes": xyxy 형식,
                "labels": category id,
                "label_names": 클래스명 리스트
                "image_path": 이미지 파일 경로
                }
    """
    boxes, labels, label_names = [], [], []
    img_filename = None

    for sub_folder in os.listdir(annot_folder_path):
        sub_path = os.path.join(annot_folder_path, sub_folder)
        if not os.path.isdir(sub_path):
            continue

        for json_file in os.listdir(sub_path):
            if not json_file.endswith(".json"):
                continue

            json_path = os.path.join(sub_path, json_file)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if img_filename is None:
                img_filename = data["images"][0]["file_name"]

            categories = {cat["id"]: cat["name"] for cat in data["categories"]}

            for ann in data["annotations"]:
                x, y, w, h = ann["bbox"]
                boxes.append([x, y, x + w, y + h])
                labels.append(ann["category_id"])
                label_names.append(categories[ann["category_id"]])

    img_path = os.path.join(image_dir, img_filename)
    image = Image.open(img_path).convert("RGB")

    target = {
        "boxes": torch.tensor(boxes, dtype=torch.float32),
        "labels": torch.tensor(labels, dtype=torch.int64),
        "label_names": label_names,
        "image_path": img_path,
    }

    return image, target


def build_color_palette(num_classes: int) -> list[tuple[float, float, float]]:
    """
    클래스 수에 맞게 색상 구분

    Args:
        num_classes (int): 생성할 색상 수(클래스 수)

    Returns:
        list[tuple[float, float, float]]: RGB 색상 (0~1범위)
    """
    colors = []
    for i in range(num_classes):
        hue = (i * 137.508) % 360 / 360
        s, v = 0.75, 0.95
        h = hue * 6
        c = v * s
        x = c * (1 - abs(h % 2 - 1))
        m = v - c
        if h < 1:
            r, g, b = c, x, 0
        elif h < 2:
            r, g, b = x, c, 0
        elif h < 3:
            r, g, b = 0, c, x
        elif h < 4:
            r, g, b = 0, x, c
        elif h < 5:
            r, g, b = x, 0, c
        else:
            r, g, b = c, 0, x
        colors.append((r + m, g + m, b + m))
    return colors


def visualize_sample(
    image,
    target: dict,
    ax: plt.Axes | None = None,
    show_labels: bool = True,
    line_width: float = 2.0,
    font_size: float = 9.0,
    num_classes: int = 56,
    palette: list[tuple[float, float, float]] | None = None,
) -> plt.Axes:
    """
    이미지 위에 바운딩 박스와 클래스 라벨 시각화

    Args:
        image : 시각화 이미지(PIL.Image, numpy.array)
        target (dict): 바운딩 박스 정보
                       - "boxes": (N, 4) 형태, xyxy 좌표 (Tensor 또는 ndarray)
                       - "labels": (N,) 형태, 카테고리 ID (Tensor 또는 list)
                       - "label_names": 클래스명 리스트
                       - "image_path": 이미지 파일 경로 (타이틀 표시용, 선택)
        ax (plt.Axes | None): 그릴 Axes 객체. None이면 새로 생성.
        show_labels (bool): 클래스명 텍스트화 여부(기본값: True)
        line_width (float):  바운딩 박스 선 두께(기본값: 2.0)
        font_size (float): 라벨 텍스트 글씨 크기(기본값: 9.0)
        num_classes (int): 색상 팔레트 사용할 때의 클래스 수(기본값: 56)
        palette (list[tuple[float, float, float]] | None): 사전 정의 함수 색상 팔레트(기본값: None)

    Returns:
        plt.Axes: 바운딩 박스가 그려진 Axes 객체
    """
    img_np = np.array(image)

    if ax is None:
        _, ax = plt.subplots(1, 1, figsize=(8, 8))

    ax.imshow(img_np)
    ax.axis("off")

    boxes = target.get("boxes")
    labels = target.get("labels")
    label_names = target.get("label_names", [])

    if boxes is None or (hasattr(boxes, "__len__") and len(boxes) == 0):
        return ax

    if isinstance(boxes, torch.Tensor):
        boxes = boxes.cpu().numpy()
    if isinstance(labels, torch.Tensor):
        labels = labels.cpu().tolist()

    colors = palette if palette is not None else build_color_palette(num_classes)

    for box, label_id, name in zip(boxes, labels or [], label_names):
        x1, y1, x2, y2 = box
        color = colors[int(label_id) % len(colors)]

        rect = patches.Rectangle(
            (x1, y1),
            x2 - x1,
            y2 - y1,
            linewidth=line_width,
            edgecolor=color,
            facecolor="none",
        )
        ax.add_patch(rect)

        if show_labels and name:
            ax.text(
                x1,
                y1 - 4,
                name,
                color="white",
                fontsize=font_size,
                fontweight="bold",
                bbox=dict(facecolor=color, edgecolor="none", pad=1.5, alpha=0.85),
                clip_on=True,
            )

    image_path = target.get("image_path", "")
    if image_path:
        ax.set_title(str(image_path).split("\\")[-1].split("/")[-1], fontsize=10)

    return ax

def collect_all_json(annot_dir: Path) -> list[Path]:
    """
    annot_dir에 있는 모든 json 파일 경로 수집

    Args:
        annot_dir (Path): json 파일이 있는 최상위 폴더 경로

    Returns:
        list[Path]: 모든 json 파일 경로
    """
    json_files = list(annot_dir.rglob("*.json"))
    return json_files

def build_category_map(json_files: list[Path]) -> tuple[dict[int, int], dict[int, int]]:
    """
    전체 json 파일에서 category_id + name 수집,
    0부터 시작하는 클래스 인덱스로 매핑

    Args:
        json_files (list[Path]): collect_all_json으로 수집한 json 파일

    Returns:
        cat_map: dict{원본 category_id: 클래스 인텍스},
        id_ to_name: dict{원본 category_id: 클래스명}
    """
    category_ids = []
    id_to_name = {}
    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)
        for cat in data.get("categories", []):
            category_ids.append(cat["id"])
            id_to_name[cat["id"]] = cat["name"]

    sorted_ids = sorted(category_ids)
    cat_map = {original: idx for idx, original in enumerate(sorted_ids)}
    return cat_map, id_to_name

def coco_to_yolo(bbox: list, img_w: int, img_h:int) -> tuple:
    """
    COCO 포맷(x, y, w, h) -> YOLO(cx, cy, w, h)로 변환

    Args:
        bbox (list): COCO(x_min, y_min, w, h)
        img_w (int): 이미지 가로 길이
        img_h (int): 이미지 세로 길이

    Returns:
        tuple: {cx, cy, nw, nh} 정규화된 YOLO 포맷
    """
    x_min, y_min, w, h = bbox
    cx = (x_min + w / 2) / img_w
    cy = (y_min + h / 2) / img_h
    nw = w / img_w
    nh = h / img_h

    cx, cy, nw, nh = (
        min(max(cx, 0), 1),
        min(max(cy, 0), 1),
        min(max(nw, 0), 1),
        min(max(nh, 0), 1),
    ) 

    return cx, cy, nw, nh

def convert_annotations(
        json_files: list[Path],
        cat_map: dict[int, int],
) -> set[str]:
    """
    각 json 파일 YOLO로 변환 후,
    json 파일과 동일한 위치에 .txt로 저장

    Args:
        json_files (list[Path]): collect_all_json으로 수집한 json 파일
        cat_map (dict[int, int]): build_category_map 으로 만든 category_id + 클래스 인덱스

    Returns:
        set[str]: 새로 생성된 txt 파일 경로
    """
    converted: set[str] = set()

    for jf in json_files:
        with open(jf) as f:
            data = json.load(f)

        images = {img["id"]: img for img in data["images"]}
        lines = []                                                      # txt 파일에 쓸 텍스트

        for ann in data["annotations"]:
            img = images[ann["image_id"]]
            img_w, img_h = img["width"], img["height"]
            cls = cat_map[ann["category_id"]]
            cx, cy, nw, nh = coco_to_yolo(ann["bbox"], img_w, img_h)
            lines.append(f"{cls} {cx:.0f} {cy:.0f} {nw:.0f} {nh:.0f}\n")
            txt_path = jf.with_suffix(".txt")
            txt_path.write_text("".join(lines), encoding="utf-8")
            converted.add(str(txt_path))

    return converted