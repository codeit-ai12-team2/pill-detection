//
//  PillDetail.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/9/26.
//

import Foundation
import SwiftData

/// pill_detail_mapping.csv의 한 행. 알약의 성분·효능·복용 정보.
@Model
final class PillDetail {
    /// 낱알식별 API의 품목일련번호. 중복 저장 방지를 위해 unique.
    @Attribute(.unique) var itemSeq: String
    var dlName: String
    var ingredient: String
    var effect: String
    /// dosage_all을 '/' 기준으로 나눈 용법 목록
    var dosages: [String]
    var time: String
    var warning: String

    init(
        itemSeq: String,
        dlName: String,
        ingredient: String,
        effect: String,
        dosages: [String],
        time: String,
        warning: String
    ) {
        self.itemSeq = itemSeq
        self.dlName = dlName
        self.ingredient = ingredient
        self.effect = effect
        self.dosages = dosages
        self.time = time
        self.warning = warning
    }

    /// itemSeq → 첫 번째 용법. dosage_all이 비어 있는 알약은 결과에 포함되지 않는다.
    static func firstDosages(
        for itemSeqs: [String],
        context: ModelContext
    ) throws -> [String: String] {
        guard !itemSeqs.isEmpty else { return [:] }

        let descriptor = FetchDescriptor<PillDetail>(
            predicate: #Predicate { itemSeqs.contains($0.itemSeq) }
        )
        return try context.fetch(descriptor).reduce(into: [:]) { result, detail in
            if let first = detail.dosages.first {
                result[detail.itemSeq] = first
            }
        }
    }

    /// CSV 문자열을 파싱한다. 형식이 어긋난 행은 건너뛴다.
    /// 파일을 어디서 읽어올지는 호출부(조립 지점)의 책임이다.
    static func parse(csv: String) -> [PillDetail] {
        csv
            .split(whereSeparator: \.isNewline)
            .dropFirst() // 헤더
            .compactMap { line in
                let columns = parseLine(line)
                guard columns.count >= 7, !columns[0].isEmpty else { return nil }

                let dosages = columns[4]
                    .split(separator: "/")
                    .map { $0.trimmingCharacters(in: .whitespaces) }

                return PillDetail(
                    itemSeq: columns[0],
                    dlName: columns[1],
                    ingredient: columns[2],
                    effect: columns[3],
                    dosages: dosages,
                    time: columns[5],
                    warning: columns[6]
                )
            }
    }

    /// CSV 한 행을 컬럼으로 나눈다.
    /// "아세트아미노펜, 클로르족사존"처럼 따옴표로 감싼 필드 안의 콤마는 구분자로 취급하지 않는다.
    private static func parseLine(_ line: some StringProtocol) -> [String] {
        var columns: [String] = []
        var current = ""
        var isInQuotes = false

        for character in line {
            switch character {
            case "\"":
                isInQuotes.toggle()
            case "," where !isInQuotes:
                columns.append(current)
                current = ""
            default:
                current.append(character)
            }
        }
        columns.append(current)

        return columns.map { $0.trimmingCharacters(in: .whitespaces) }
    }
}
