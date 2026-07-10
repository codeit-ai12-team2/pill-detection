//
//  PillInfoVM.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import Foundation
import Observation
import SwiftData
import os

private let logger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "Pillaw",
    category: "PillInfoVM"
)

@Observable
final class PillInfoVM {
    /// 낱알식별 API 기반 정보 (이름, 이미지, 즐겨찾기)
    private(set) var pill: Pill?

    /// pill_detail_mapping.csv 기반 정보 (성분, 효능, 용법, 시간, 주의)
    private(set) var detail: PillDetail?

    var isFavorite: Bool {
        pill?.isFavorite ?? false
    }

    /// itemSeq로 저장된 알약 정보를 불러온다.
    /// 다른 화면에서 토글한 즐겨찾기를 반영하기 위해 화면이 나타날 때마다 호출한다.
    func load(itemSeq: String, context: ModelContext) {
        do {
            var pillDescriptor = FetchDescriptor<Pill>(
                predicate: #Predicate { $0.itemSeq == itemSeq }
            )
            pillDescriptor.fetchLimit = 1
            pill = try context.fetch(pillDescriptor).first

            var detailDescriptor = FetchDescriptor<PillDetail>(
                predicate: #Predicate { $0.itemSeq == itemSeq }
            )
            detailDescriptor.fetchLimit = 1
            detail = try context.fetch(detailDescriptor).first
        } catch {
            logger.error("알약 정보 조회 실패: \(String(describing: error), privacy: .public)")
            pill = nil
            detail = nil
        }
    }

    func toggleFavorite() {
        pill?.toggleFavorite()
    }
}
