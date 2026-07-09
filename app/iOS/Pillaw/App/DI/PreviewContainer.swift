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
        CameraVM(
            cameraRepo: CameraRepoImpl(
                detector: PillDetectorRepoImpl(mappings: [])
            )
        )
    }

    func makeFavoriteVM() -> FavoriteVM {
        FavoriteVM()
    }

    func makeSplashVM() -> SplashVM {
        SplashVM(
            pillRepo: PillRepoImpl(networkClient: NetworkClientImpl()),
            classMappingCSV: """
            class_index,dl_name,category_id,item_seq
            0,보령부스파정 5mg,1900,198700706
            """,
            pillDetailCSV: """
            item_seq,dl_name,ingredient,effect,dosage_all,time,warning
            198700706,보령부스파정 5mg,부스피론염산염,불안장애 치료 및 완화,1일 3회 1정,,
            """
        )
    }
}
