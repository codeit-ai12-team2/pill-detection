//
//  PillStatus.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

/// 알약 정보의 상태.
nonisolated enum PillStatus: String, Codable {
    /// API에서 정상 조회된 알약
    case normal
    /// 낱알식별 API에서 정보를 찾을 수 없는 알약
    case notFound
    /// 복용 금지 알약
    case prohibited

    /// 낱알식별 API에서 조회되지 않아 상태를 직접 지정하는 알약들 (item_seq 기준).
    /// 시딩 시 API 호출 없이 이 상태로 저장됩니다.
    static let overrides: [String: PillStatus] = [
        "200500251": .notFound,   // 가바토파정 100mg
        "199201807": .prohibited, // 뉴로메드정(옥시라세탐)
        "200611524": .notFound,   // 마도파정
        "200902214": .prohibited  // 큐시드정 31.5mg/PTP
    ]

    var displayName: String {
        switch self {
        case .normal: "정상"
        case .notFound: "정보를 찾을 수 없음"
        case .prohibited: "복용 금지"
        }
    }
}
