//
//  CameraView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI
import SwiftData

struct CameraView: View {
    @Environment(\.openURL)
    private var openURL

    @Environment(\.modelContext)
    private var modelContext

    @State
    private var vm: CameraVM

    init(vm: CameraVM) {
        _vm = State(initialValue: vm)
    }

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            switch vm.permission {
            case .unknown:
                ProgressView()
                    .tint(.white)
            case .granted:
                CameraPreview(session: vm.session)
                    .ignoresSafeArea()
                if vm.showsBoundingBoxes {
                    boundingBoxOverlay
                        .ignoresSafeArea()
                        .allowsHitTesting(false)
                }
            case .denied:
                permissionDeniedView
            }
        }
        .overlay(alignment: .bottom) {
            if vm.permission == .granted {
                detectedPillList
            }
        }
        .navigationTitle("Camera")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if vm.permission == .granted, vm.isDetectionAvailable {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        vm.showsBoundingBoxes.toggle()
                    } label: {
                        Image(
                            systemName: vm.showsBoundingBoxes
                                ? "rectangle.dashed.badge.record"
                                : "rectangle.dashed"
                        )
                    }
                }
            }
        }
        .task {
            await vm.startCamera()
        }
        .task {
            await vm.startDetection(context: modelContext)
        }
        .onDisappear {
            Task {
                await vm.stopCamera()
            }
        }
    }

    /// 프리뷰(aspect-fill) 위에 감지 bbox를 그린다.
    private var boundingBoxOverlay: some View {
        GeometryReader { geometry in
            let content = aspectFillRect(for: vm.detectionFrameSize, in: geometry.size)
            ForEach(vm.detectionBoxes) { box in
                let rect = CGRect(
                    x: content.minX + box.rect.minX * content.width,
                    y: content.minY + box.rect.minY * content.height,
                    width: box.rect.width * content.width,
                    height: box.rect.height * content.height
                )
                RoundedRectangle(cornerRadius: 4)
                    .stroke(.yellow, lineWidth: 2)
                    .overlay(alignment: .topLeading) {
                        Text("\(box.name ?? "?") \(Int(box.confidence * 100))%")
                            .font(.caption2.bold())
                            .foregroundStyle(.black)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 2)
                            .background(.yellow, in: .rect(cornerRadius: 4))
                            .fixedSize()
                            // 라벨을 박스 위쪽에 얹는다
                            .alignmentGuide(.top) { $0[.bottom] }
                    }
                    .frame(width: rect.width, height: rect.height)
                    .position(x: rect.midX, y: rect.midY)
            }
        }
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

    @ViewBuilder
    private var detectedPillList: some View {
        if !vm.isDetectionAvailable {
            Text("감지 모델이 아직 준비되지 않았어요.")
                .font(.caption)
                .foregroundStyle(.white)
                .padding(8)
                .background(.black.opacity(0.5), in: .capsule)
                .padding(.bottom, 16)
        } else if !vm.detectedPills.isEmpty {
            ScrollView {
                LazyVStack(spacing: 8) {
                    ForEach(vm.detectedPills, id: \.itemSeq) { pill in
                        PillCardView(pill: pill)
                    }
                }
                .padding(12)
            }
            .frame(maxHeight: 220)
            .background(.ultraThinMaterial, in: .rect(cornerRadius: 20))
            .padding(.horizontal, 16)
            .padding(.bottom, 16)
        }
    }

    private var permissionDeniedView: some View {
        VStack(spacing: 16) {
            Image(systemName: "camera.fill")
                .font(.largeTitle)
                .foregroundStyle(.white)
            Text("Camera access is required to detect pills.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.white)
            Button("Open Settings") {
                if let url = URL(string: UIApplication.openSettingsURLString) {
                    openURL(url)
                }
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}

#Preview {
    NavigationStack {
        CameraView(
            vm: PreviewContainer.shared.makeCameraVM()
        )
    }
}
