//
//  PillRepo.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

nonisolated protocol PillRepo {
    /// item_seq로 낱알식별 정보를 조회해 첫 번째 결과를 반환한다.
    func fetchPill(itemSeq: String) async throws -> PillDTO?
}
