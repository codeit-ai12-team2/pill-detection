//
//  GovResponse.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

/// 공공데이터포털 공통 응답 래퍼 (`type=json` 기준).
nonisolated struct GovResponse<Item: Decodable>: Decodable {
    let header: Header
    let body: Body?

    var isSuccess: Bool { header.resultCode == "00" }
    var items: [Item] { body?.items ?? [] }
    var totalCount: Int { body?.totalCount ?? 0 }
    var pageNo: Int { body?.pageNo ?? 0 }
    var numOfRows: Int { body?.numOfRows ?? 0 }

    nonisolated struct Header: Decodable {
        let resultCode: String
        let resultMsg: String
    }

    nonisolated struct Body: Decodable {
        let pageNo: Int
        let totalCount: Int
        let numOfRows: Int
        let items: [Item]?
    }
}
