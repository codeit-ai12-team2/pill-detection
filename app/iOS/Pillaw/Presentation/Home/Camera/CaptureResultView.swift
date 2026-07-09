//
//  CaptureResultView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI

/// 촬영된 정지 프레임 위에 번호가 매겨진 bounding box를 그리는 결과 화면.
struct CaptureResultView: View {
    let image: CGImage?
    /// 촬영 프레임 크기(픽셀). bbox를 aspect-fill 화면 좌표로 변환할 때 사용.
    let frameSize: CGSize
    let detections: [CameraVM.CapturedDetection]
    let onClose: () -> Void

    /// bbox와 번호 뱃지 색상
    var boxColor: Color = .danube
    /// bbox 모서리 radius
    var boxCornerRadius: CGFloat = 16

    var body: some View {
        ZStack {
            GeometryReader { geometry in
                let content = aspectFillRect(for: frameSize, in: geometry.size)

                if let image {
                    Image(decorative: image, scale: 1)
                        .resizable()
                        .frame(width: content.width, height: content.height)
                        .position(x: content.midX, y: content.midY)
                }

                ForEach(detections) { detection in
                    boundingBox(for: detection, in: content)
                }
            }
            .ignoresSafeArea()

            CameraLayoutView(
                showsFlash: false,
                showsCapture: false,
                onClose: onClose
            )
        }
    }

    private func boundingBox(
        for detection: CameraVM.CapturedDetection,
        in content: CGRect
    ) -> some View {
        let rect = CGRect(
            x: content.minX + detection.rect.minX * content.width,
            y: content.minY + detection.rect.minY * content.height,
            width: detection.rect.width * content.width,
            height: detection.rect.height * content.height
        )
        return RoundedRectangle(cornerRadius: boxCornerRadius)
            .stroke(boxColor, lineWidth: 3)
            .overlay(alignment: .topLeading) {
                NumberBadge(number: detection.number, bgColor: boxColor)
                    // 원의 중심이 bbox 왼쪽 상단 모서리에 오도록
                    .offset(x: -12, y: -12)
            }
            .frame(width: rect.width, height: rect.height)
            .position(x: rect.midX, y: rect.midY)
    }

    /// 프레임이 aspect-fill로 표시될 때 화면에서 차지하는 영역 (화면 밖으로 벗어난 부분 포함)
    private func aspectFillRect(for frameSize: CGSize, in viewSize: CGSize) -> CGRect {
        guard frameSize.width > 0, frameSize.height > 0 else {
            return CGRect(origin: .zero, size: viewSize)
        }
        let scale = max(
            viewSize.width / frameSize.width,
            viewSize.height / frameSize.height
        )
        let size = CGSize(
            width: frameSize.width * scale,
            height: frameSize.height * scale
        )
        return CGRect(
            x: (viewSize.width - size.width) / 2,
            y: (viewSize.height - size.height) / 2,
            width: size.width,
            height: size.height
        )
    }
}

/// bbox 번호와 같은 순서로 알약 정보를 보여주는 bottom sheet 내용.
/// 시트를 아래로 내려도 title 영역은 화면에 남는다.
struct CaptureResultSheet: View {
    let detections: [CameraVM.CapturedDetection]
    let onClose: () -> Void
    let onClickItem: (Pill?) -> Void

    /// 번호 뱃지 색상 (bbox 색상과 맞춰 쓴다)
    var badgeColor: Color = .danube

    var body: some View {
        VStack(spacing: 12) {
            // title 영역 — 시트를 끝까지 내렸을 때도 보이는 부분
            HStack {
                VStack(alignment: .leading, spacing: 1) {
                    Text("알약 \(detections.count)개를 찾았어요")
                        .font(.griunMongtori(size: 22))
                        .foregroundStyle(.armadillo)
                    Text("이름을 눌러 자세히 확인하세요")
                        .font(.griunMongtori(size: 15))
                        .foregroundStyle(.makara)
                }
                Spacer()
                HStack(spacing: 6) {
                    Image(.icRecapture)
                        .resizable()
                        .frame(width: 13, height: 12)
                    Button(action: onClose) {
                        Text("다시 촬영")
                            .font(.griunMongtori(size: 15))
                            .foregroundStyle(.soyaBean)
                    }
                }
                .padding(.horizontal, 15)
                .padding(.vertical, 12)
                .background(.linen)
                .clipShape(Capsule())
            }
            .padding(.horizontal, 20)
            .padding(.top, 18)

            ScrollView {
                LazyVStack(spacing: 12) {
                    ForEach(detections) { detection in
                        Button(action: {
                            onClickItem(detection.pill)
                        }) {
                            HStack(spacing: 14) {
                                NumberBadge(
                                    number: detection.number,
                                    bgColor: .hawkesBlue,
                                    fontColor: .steelBlue,
                                    size: 32
                                )
                                if let pill = detection.pill {
                                    VStack(alignment: .leading) {
                                        Text(pill.itemName)
                                            .font(.griunMongtori(size: 19))
                                            .foregroundStyle(.armadillo)
                                        // - FIX: 알약 복용 정보 연동
                                        PillDurationView()
                                    }
                                    Spacer()
                                    Image(.icArrowRight)
                                        .resizable()
                                        .frame(width: 6.75, height: 12.38)
                                } else {
                                    Text("정보를 찾을 수 없는 알약이에요")
                                        .font(.griunMongtori(size: 15))
                                        .foregroundStyle(.secondary)
                                    Spacer()
                                }
                            }
                        }
                        if detection != detections.last {
                            Divider()
                                .frame(height: 2)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.vertical, 12)
            }
        }
    }
}

/// bbox 왼쪽 상단과 목록에 함께 쓰이는 원형 번호 뱃지.
struct NumberBadge: View {
    let number: Int
    let bgColor: Color
    var fontColor: Color = .white
    var size: CGFloat = 26

    var body: some View {
        Text("\(number)")
            .font(.griunMongtori(size: 14))
            .foregroundStyle(fontColor)
            .frame(width: size, height: size)
            .background(bgColor, in: .circle)
    }
}

#Preview("결과 화면") {
    CaptureResultView(
        image: nil,
        frameSize: CGSize(width: 1080, height: 1920),
        detections: [
            .init(number: 1, rect: CGRect(x: 0.2, y: 0.2, width: 0.3, height: 0.15), pill: Pill(), confidence: 0.9),
            .init(number: 2, rect: CGRect(x: 0.5, y: 0.5, width: 0.25, height: 0.12), pill: nil, confidence: 0.8)
        ],
        onClose: {}
    )
    .background(.black)
}

#Preview("결과 시트") {
    CaptureResultSheet(
        detections: [
            .init(number: 1, rect: .zero, pill: Pill(), confidence: 0.9),
            .init(number: 2, rect: .zero, pill: nil, confidence: 0.8)
        ],
        onClose: {},
        onClickItem: {_ in }
    )
}
