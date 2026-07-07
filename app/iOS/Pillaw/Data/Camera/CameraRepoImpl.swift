//
//  CameraRepoImpl.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import AVFoundation

nonisolated final class CameraRepoImpl: CameraRepo, @unchecked Sendable {
    let session = AVCaptureSession()

    private let sessionQueue = DispatchQueue(label: "com.pillaw.camera.session")

    private var isConfigured = false
    private var isRunning = false
    private var pendingStop: DispatchWorkItem?
    // 재진입시 2초 delay
    private let stopDelay: TimeInterval = 2

    func requestPermission() async -> Bool {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized:
            return true
        case .notDetermined:
            return await AVCaptureDevice.requestAccess(for: .video)
        default:
            return false
        }
    }

    func start() async {
        await withCheckedContinuation { continuation in
            sessionQueue.async { [self] in
                pendingStop?.cancel()
                pendingStop = nil

                if !isConfigured {
                    configureSession()
                    isConfigured = true
                }

                if !isRunning {
                    session.startRunning()
                    isRunning = true
                }

                continuation.resume()
            }
        }
    }

    func stop() async {
        sessionQueue.async { [self] in
            pendingStop?.cancel()

            let work = DispatchWorkItem { [weak self] in
                guard let self, self.isRunning else { return }
                self.session.stopRunning()
                self.isRunning = false
            }
            pendingStop = work
            sessionQueue.asyncAfter(deadline: .now() + stopDelay, execute: work)
        }
    }

    private func configureSession() {
        session.beginConfiguration()
        defer { session.commitConfiguration() }

        session.sessionPreset = .high

        guard
            let device = AVCaptureDevice.default(
                .builtInWideAngleCamera,
                for: .video,
                position: .back
            ),
            let input = try? AVCaptureDeviceInput(device: device),
            session.canAddInput(input)
        else { return }

        session.addInput(input)
    }
}
