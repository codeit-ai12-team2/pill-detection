//
//  CameraVM.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import AVFoundation
import Observation

@Observable
final class CameraVM {
    enum PermissionState {
        case unknown
        case granted
        case denied
    }

    private let cameraRepo: CameraRepo

    var permission: PermissionState = .unknown

    var session: AVCaptureSession {
        cameraRepo.session
    }

    init(cameraRepo: CameraRepo) {
        self.cameraRepo = cameraRepo
    }

    func startCamera() async {
        guard await cameraRepo.requestPermission() else {
            permission = .denied
            return
        }
        permission = .granted
        await cameraRepo.start()
    }

    func stopCamera() async {
        await cameraRepo.stop()
    }
}
