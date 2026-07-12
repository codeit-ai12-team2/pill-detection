# 💊 Pill-Detection

<div align="center">
  <img src=".images/banner_image.png" width="100%">
</div>

Repo URL : [![Repo](https://img.shields.io/badge/GitHub-Repository-181717?style=flat&logo=github)](https://github.com/codeit-ai12-team2/pill-detection)

<br/>

## 📋 Project Overview

헬스케어 스타트업 **헬스잇(Health Eat)** 의 AI 엔지니어링 팀을 가정하여, 모바일 앱 기반 알약 인식 서비스의 핵심 모델을 개발하는 프로젝트입니다.

약사가 아닌 일반 유저는 본인이 복용 중인 약의 이름이나 종류, 함께 복용하면 안 되는 약의 조합 등을 정확히 알기 어렵다는 것이 현재의 문제입니다.

유저가 약을 모바일로 촬영하면 이러한 정보를 자동으로 제공할 수 있다면, 유저의 건강 상태 관리는 물론 병용 금지 약물 안내 등 헬스케어 서비스로서의 비즈니스 가치를 창출할 수 있습니다.

따라서 이미지 한 장에 담긴 최대 4개의 알약을 대상으로 **클래스** 와 **바운딩 박스** 를 검출하는 Object Detection 모델을 구현하고, 실사용이 가능한 수준까지 성능을 고도화합니다.

<br/>

## 🎬 Demo

<div align="center">

[![시연 영상](https://img.youtube.com/vi/gA4zGYYqIOQ/hqdefault.jpg)](https://www.youtube.com/watch?v=gA4zGYYqIOQ)

<sub> < 알약 사진을 촬영하면 이름과 위치를 인식하는 애플리케이션 시연 영상입니다. > </sub>

</div>

<br/>

## 😄 Team Member

<div align="center">

<table>
    <tr align="center">
        <td><img src=".images/ws_image.jpeg" width="120" height="120" style="border-radius:50%;"></td>
        <td><img src=".images/ch_image.jpg" width="120" height="120" style="border-radius:50%;"></td>
        <td><img src=".images/hj_image.jpg" width="120" height="120" style="border-radius:50%;"></td>
        <td><img src=".images/sw_image.jpg" width="120" height="120" style="border-radius:50%;"></td>
    </tr>
    <tr align="center">
        <td><b>김완수/PM</b></td>
        <td><b>안찬형</b></td>
        <td><b>임현진</b></td>
        <td><b>최승원</b></td>
    </tr>
    <tr align="center">
        <td>
            <img src="https://img.shields.io/badge/Data Researcher-2E8B57?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Model Architect-1E6FD9?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Evaluation Analyst-E67E22?style=flat-square">
        </td>
        <td>
            <img src="https://img.shields.io/badge/Data Researcher-2E8B57?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Model Architect-1E6FD9?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Evaluation Analyst-E67E22?style=flat-square">
        </td>
        <td>
            <img src="https://img.shields.io/badge/Data Researcher-2E8B57?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Model Architect-1E6FD9?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Evaluation Analyst-E67E22?style=flat-square">
        </td>
        <td>
            <img src="https://img.shields.io/badge/Data Researcher-2E8B57?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Model Architect-1E6FD9?style=flat-square"><br/>
            <img src="https://img.shields.io/badge/Evaluation Analyst-E67E22?style=flat-square">
        </td>
    </tr>
</table>

</div>

<br/>

## 🔗 Reference

| 문서 | 링크 |
| :--: | :--: |
| 📎 EDA README | [바로가기](ai/README.md) |
| 📎 app/iOS README | [바로가기](app/iOS/README.md) |

<br/>

## 🗂️ Project Structure

```
📦 pill-detection
┣ 📂 .images
┣ 📂 ai
┃ ┣ 📂 outputs
┃ ┃ ┣ 📂 yolo11s
┃ ┃ ┣ 📂 yolo26l-17
┃ ┃ ┣ 📂 yolo26l-21
┃ ┃ ┣ 📂 yolo26l
┃ ┃ ┗ 📂 yolo26s
┃ ┣ 📂 src
┃ ┃ ┣ 📂 rt_detr
┃ ┃ ┣ 📂 util
┃ ┃ ┣ 📂 visual
┃ ┃ ┣ 📂 yolo
┃ ┃ ┣ 📂 yolo26l_refine
┃ ┃ ┣ 📝 dataset.py
┃ ┃ ┗ 📝 init.py
┃ ┣ 📃 README.md
┃ ┣ 📃 requirements.txt
┃ ┣ 📃 requirements_for_runpod.txt
┃ ┗ 📃 requirements_for_runpod 2.txt
┣ 📂 app/iOS
┃ ┣ 📂 Pillaw.xcodeproj
┃ ┣ 📂 Pillaw
┃ ┣ 📂 PillawTests
┃ ┣ 📂 PillawUITests
┃ ┗ 📃 README.md
┗ 📃 README.md
```

<br/>

## 🌿 Team Git Rule's

### ✅ Code Style

`Black` or `Ruff` 확장 프로그램 사용

### ✍️ Comments

- Google Style  
- 간단한 method의 경우 `$DESCRIPTION$`만 사용

```python
"""
$DESCRIPTION$

Args:
    $PARAMS$: param

Returns:
    $RETURN$:

Raises:
    $EXCEPTION$
"""
```

### 📝 Commit Rule

| Prefix | 설명 |
| :--: | :-- |
| `feat` | 새로운 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 수정 (README 등) |
| `style` | 포맷 변경 (코드 동작 무관) |
| `refactor` | 리팩토링 |
| `test` | 테스트 추가/수정 |
| `chore` | 빌드, 패키지 설정 변경 |