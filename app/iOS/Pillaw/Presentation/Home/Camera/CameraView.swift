//
//  CameraView.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import SwiftUI

struct CameraView: View {
    @Environment(\.openURL)
    private var openURL

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
        .navigationTitle("Camera")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            await vm.startCamera()
        }
        .onDisappear {
            Task {
                await vm.stopCamera()
            }
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
