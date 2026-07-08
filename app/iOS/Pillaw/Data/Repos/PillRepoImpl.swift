//
//  PillRepoImpl.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

nonisolated final class PillRepoImpl: PillRepo {
    private let networkClient: NetworkClient

    init(networkClient: NetworkClient) {
        self.networkClient = networkClient
    }

    func fetchPill(itemSeq: String) async throws -> PillDTO? {
        let response: GovResponse<PillDTO> = try await networkClient.request(
            .pillInfo(itemSeq: itemSeq)
        )
        return response.items.first
    }
}
