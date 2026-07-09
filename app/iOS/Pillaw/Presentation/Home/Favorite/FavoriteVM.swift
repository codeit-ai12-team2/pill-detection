//
//  FavoriteVM.swift
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
    category: "FavoriteVM"
)

@Observable
final class FavoriteVM {
    /// 즐겨찾기한 알약 목록 (최근에 추가한 순)
    var favorites: [Pill] = []

    /// 즐겨찾기 목록을 다시 불러온다.
    /// 다른 화면에서 토글한 결과를 반영하기 위해 화면이 나타날 때마다 호출한다.
    func loadFavorites(context: ModelContext) {
        do {
            let descriptor = FetchDescriptor<Pill>(
                predicate: #Predicate { $0.isFavorite },
                sortBy: [SortDescriptor(\.favoritedAt, order: .reverse)]
            )
            favorites = try context.fetch(descriptor)
        } catch {
            logger.error("즐겨찾기 목록 조회 실패: \(String(describing: error), privacy: .public)")
            favorites = []
        }
    }

    /// 즐겨찾기를 해제하고 목록에서 제거한다.
    func removeFavorite(_ pill: Pill) {
        pill.toggleFavorite()
        favorites.removeAll { $0.itemSeq == pill.itemSeq }
    }
}
