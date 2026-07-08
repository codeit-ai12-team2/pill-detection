//
//  ImagePipeline+Pillaw.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Nuke

extension ImagePipeline {
    /// 알약 이미지 전용 파이프라인.
    /// 공공 이미지 서버의 rate limit(429)에 걸리지 않도록
    /// 원본 데이터를 디스크에 캐시하고 동시 다운로드 수를 제한한다.
    static let pillImages: ImagePipeline = {
        var config = ImagePipeline.Configuration.withDataCache
        config.dataLoadingQueue = TaskQueue(maxConcurrentOperationCount: 2)
        return ImagePipeline(configuration: config)
    }()
}
