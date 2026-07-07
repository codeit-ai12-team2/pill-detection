//
//  CameraRepo.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import AVFoundation

nonisolated protocol CameraRepo {
    var session: AVCaptureSession { get }
    func requestPermission() async -> Bool
    func start() async
    func stop() async
}
