//
//  StaticCameraView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import SwiftUI
import SwiftData

struct StaticCameraView: View {
    @Environment(AppRouter.self)
    private var router
    
    @Environment(\.openURL)
    private var openURL

    @Environment(\.modelContext)
    private var modelContext

    @State
    private var vm: CameraVM

    @State
    private var sheetDetent: PresentationDetent = .medium

    /// 카메라 프리뷰가 실제로 표시되는 화면 크기 (safe area 포함).
    /// 캡처 시 화면 밖에서 감지된 알약을 걸러내는 데 쓴다.
    @State
    private var previewSize: CGSize = .zero

    /// 알약 상세 화면으로 이동하는 동안 시트를 숨기기 위한 플래그.
    /// 촬영 결과는 유지되므로 돌아오면 시트가 같은 내용으로 다시 나타난다.
    @State
    private var isNavigatingToDetail = false

    /// 시트를 끝까지 내렸을 때 title 영역만 남는 높이
    private let collapsedDetent = PresentationDetent.height(76)

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
                grantedContent
            case .denied:
                permissionDeniedView
            }
        }
        .toolbar(.hidden, for: .navigationBar)
        .onGeometryChange(for: CGSize.self) { proxy in
            // 프리뷰는 safe area를 무시하고 화면 전체를 채우므로 inset을 포함해 계산한다
            CGSize(
                width: proxy.size.width + proxy.safeAreaInsets.leading + proxy.safeAreaInsets.trailing,
                height: proxy.size.height + proxy.safeAreaInsets.top + proxy.safeAreaInsets.bottom
            )
        } action: { size in
            previewSize = size
        }
        .task {
            await vm.startCamera()
        }
        .onAppear {
            // 상세 화면에서 돌아오면 유지된 촬영 결과로 시트를 다시 띄운다
            isNavigatingToDetail = false
        }
        .onDisappear {
            Task {
                await vm.stopCamera()
            }
        }
        .sheet(isPresented: isResultPresented) {
            CaptureResultSheet(
                detections: vm.capturedDetections,
                onClose: { vm.returnToCamera() },
                onClickItem: { pill in
                    isNavigatingToDetail = true
                    if let pill = pill {
                        if (pill.status == .normal) {
                            router.push(.pillInfo(id: pill.itemSeq))
                        } else {
                            router.push(.pillInfoBanned)
                        }
                    } else {
                        router.push(.pillInfoBanned)
                    }
                }
            )
                .presentationDetents(
                    [collapsedDetent, .medium, .large],
                    selection: $sheetDetent
                )
                .presentationBackgroundInteraction(.enabled(upThrough: .medium))
                .presentationDragIndicator(.visible)
                .interactiveDismissDisabled()
        }
    }

    /// 촬영 전에는 라이브 카메라, 촬영 후에는 정지 프레임 + 감지 결과 화면으로 전환한다.
    @ViewBuilder
    private var grantedContent: some View {
        switch vm.mode {
        case .camera:
            CameraPreview(session: vm.session)
                .ignoresSafeArea()
            CameraLayoutView (
                onClose: {
                    router.pop()
                },
                onFlash: {
                    Task { await vm.toggleTorch() }
                },
                onCapture: {
                    sheetDetent = .medium
                    Task { await vm.capture(viewSize: previewSize, context: modelContext) }
                }
            )
        case .result:
            CaptureResultView(
                image: vm.capturedImage,
                frameSize: vm.capturedFrameSize,
                detections: vm.capturedDetections,
                onClose: { vm.returnToCamera() }
            )
        }
    }

    /// result 모드에서만 시트를 띄운다. 상세 화면으로 이동 중에는 숨긴다.
    /// 스와이프로는 title 영역(collapsedDetent)까지만 줄어들고, close 버튼으로만 닫힌다.
    private var isResultPresented: Binding<Bool> {
        Binding(
            get: { vm.mode == .result && !isNavigatingToDetail },
            set: { isPresented in
                if !isPresented && !isNavigatingToDetail { vm.returnToCamera() }
            }
        )
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
        StaticCameraView(
            vm: PreviewContainer.shared.makeCameraVM()
        )
    }
    .environment(AppRouter())
}
