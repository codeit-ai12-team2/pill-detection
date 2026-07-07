//
//  PreviewContainer.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

final class PreviewContainer {
    static let shared = PreviewContainer()

    func makeHomeVM() -> HomeVM {
        HomeVM()
    }

    func makeCameraVM() -> CameraVM {
        CameraVM(cameraRepo: CameraRepoImpl())
    }
}
