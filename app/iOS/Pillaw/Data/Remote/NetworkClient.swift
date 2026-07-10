//
//  NetworkClient.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

nonisolated protocol NetworkClient {
    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T
    func requestData(_ endpoint: Endpoint) async throws -> Data
}
