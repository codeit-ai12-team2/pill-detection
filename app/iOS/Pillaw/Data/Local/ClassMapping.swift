//
//  ClassMapping.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Foundation

/// class_mapping.csv의 한 행.
/// YOLO 클래스 인덱스와 낱알식별 API의 item_seq를 이어준다.
nonisolated struct ClassMapping {
    let classIndex: Int
    let dlName: String
    let categoryId: String
    let itemSeq: String

    /// CSV 문자열을 파싱한다. 형식이 어긋난 행은 건너뛴다.
    /// 파일을 어디서 읽어올지는 호출부(조립 지점)의 책임이다.
    static func parse(csv: String) -> [ClassMapping] {
        csv
            .split(whereSeparator: \.isNewline)
            .dropFirst() // 헤더
            .compactMap { line in
                let columns = line
                    .split(separator: ",", omittingEmptySubsequences: false)
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                guard columns.count >= 4, let classIndex = Int(columns[0]) else {
                    return nil
                }
                return ClassMapping(
                    classIndex: classIndex,
                    dlName: columns[1],
                    categoryId: columns[2],
                    itemSeq: columns[3]
                )
            }
    }
}
