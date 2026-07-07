//
//  API.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

/// The remote services the app talks to. Each case carries its own base URL
/// and default auth, so one NetworkClient can serve them all.
nonisolated enum API {
    /// 의약품 정보 조회 API
    case pillInfo

    var baseURLString: String {
        switch self {
        case .pillInfo:
            // TODO: 실제 사용할 API의 base URL로 교체
            "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService02"
        }
    }

    /// Query items this API requires on every request (e.g. service keys).
    var defaultQueryItems: [URLQueryItem] {
        switch self {
        case .pillInfo:
            [URLQueryItem(name: "serviceKey", value: Secrets.pillInfoAPIKey)]
        }
    }

    /// Headers this API requires on every request.
    var defaultHeaders: [String: String] {
        switch self {
        case .pillInfo:
            [:]
        }
    }
}
