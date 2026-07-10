//
//  Endpoint.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

nonisolated enum HTTPMethod: String {
    case get = "GET"
    case post = "POST"
    case put = "PUT"
    case patch = "PATCH"
    case delete = "DELETE"
}

nonisolated struct Endpoint {
    var api: API
    var path: String
    var method: HTTPMethod = .get
    var queryItems: [URLQueryItem] = []
    var headers: [String: String] = [:]
    var body: Data? = nil
}

// MARK: - 요청 정의

nonisolated extension Endpoint {
    /// 낱알식별 정보 조회. serviceKey/type/pageNo/numOfRows는
    /// API.pillInfo의 기본 쿼리로 자동 첨부된다.
    static func pillInfo(itemSeq: String) -> Endpoint {
        Endpoint(
            api: .pillInfo,
            path: "",
            queryItems: [URLQueryItem(name: "item_seq", value: itemSeq)]
        )
    }
}
