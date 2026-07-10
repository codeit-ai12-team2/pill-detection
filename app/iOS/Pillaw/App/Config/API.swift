//
//  API.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

nonisolated enum API {
    /// 의약품 정보 조회 API
    case pillInfo

    var baseURLString: String {
        switch self {
        case .pillInfo:
            "https://apis.data.go.kr/1471000/MdcinGrnIdntfcInfoService03/getMdcinGrnIdntfcInfoList03"
        }
    }

    var defaultQueryItems: [URLQueryItem] {
        switch self {
        case .pillInfo:
            [
                URLQueryItem(name: "serviceKey", value: Secrets.GOV_API_KEY),
                URLQueryItem(name: "type", value: "json"),
                URLQueryItem(name: "pageNo", value: "1"),
                URLQueryItem(name: "numOfRows", value: "10")
            ]
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
