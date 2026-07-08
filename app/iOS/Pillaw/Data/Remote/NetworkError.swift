//
//  NetworkError.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

nonisolated enum NetworkError: Error {
    case invalidURL
    case requestFailed(underlying: Error)
    case invalidResponse
    case serverError(statusCode: Int, data: Data)
    case decodingFailed(underlying: Error)
}
