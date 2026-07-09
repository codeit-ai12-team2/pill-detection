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

    /// itemSeq → 전체 용법 목록. dosage_all이 비어 있는 알약은 항목이 없다.
    private var dosages: [String: [String]] = [:]

    /// 즐겨찾기 목록을 다시 불러온다.
    /// 다른 화면에서 토글한 결과를 반영하기 위해 화면이 나타날 때마다 호출한다.
    func loadFavorites(context: ModelContext) {
        do {
            let descriptor = FetchDescriptor<Pill>(
                predicate: #Predicate { $0.isFavorite },
                sortBy: [SortDescriptor(\.favoritedAt, order: .reverse)]
            )
            favorites = try context.fetch(descriptor)
            loadDosages(context: context)
        } catch {
            logger.error("즐겨찾기 목록 조회 실패: \(String(describing: error), privacy: .public)")
            favorites = []
        }
    }

    /// 알약의 전체 용법 목록. 용법 정보가 없으면 빈 배열 (뷰에서 용법 표시를 숨긴다).
    func dosages(for pill: Pill) -> [String] {
        dosages[pill.itemSeq] ?? []
    }

    private func loadDosages(context: ModelContext) {
        let seqs = favorites.map(\.itemSeq)
        guard !seqs.isEmpty else {
            dosages = [:]
            return
        }

        do {
            let descriptor = FetchDescriptor<PillDetail>(
                predicate: #Predicate { seqs.contains($0.itemSeq) }
            )
            dosages = try context.fetch(descriptor).reduce(into: [:]) { result, detail in
                if !detail.dosages.isEmpty {
                    result[detail.itemSeq] = detail.dosages
                }
            }
        } catch {
            logger.error("알약 용법 조회 실패: \(String(describing: error), privacy: .public)")
            dosages = [:]
        }
    }

    /// 즐겨찾기를 해제하고 목록에서 제거한다.
    func removeFavorite(_ pill: Pill) {
        pill.toggleFavorite()
        favorites.removeAll { $0.itemSeq == pill.itemSeq }
    }
}
