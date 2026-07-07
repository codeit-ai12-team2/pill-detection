//
//  AppContainer.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

final class AppContainer {
    static let shared = AppContainer()

    private lazy var cameraRepo: CameraRepo = CameraRepoImpl()
    private lazy var networkClient: NetworkClient = NetworkClientImpl()

    func makeHomeVM() -> HomeVM {
        HomeVM()
    }

    func makeCameraVM() -> CameraVM {
        CameraVM(cameraRepo: cameraRepo)
    }
}
