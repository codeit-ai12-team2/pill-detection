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
