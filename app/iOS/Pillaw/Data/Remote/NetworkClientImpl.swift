//
//  NetworkClientImpl.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation

nonisolated final class NetworkClientImpl: NetworkClient, @unchecked Sendable {
    private let session: URLSession
    private let decoder: JSONDecoder

    init(session: URLSession = .shared, decoder: JSONDecoder = JSONDecoder()) {
        self.session = session
        self.decoder = decoder
    }

    func request<T: Decodable>(_ endpoint: Endpoint) async throws -> T {
        let data = try await requestData(endpoint)
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw NetworkError.decodingFailed(underlying: error)
        }
    }

    func requestData(_ endpoint: Endpoint) async throws -> Data {
        let request = try makeURLRequest(for: endpoint)

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await session.data(for: request)
        } catch {
            throw NetworkError.requestFailed(underlying: error)
        }

        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.invalidResponse
        }
        guard (200..<300).contains(httpResponse.statusCode) else {
            throw NetworkError.serverError(
                statusCode: httpResponse.statusCode,
                data: data
            )
        }

        return data
    }

    private func makeURLRequest(for endpoint: Endpoint) throws -> URLRequest {
        guard var components = URLComponents(string: endpoint.api.baseURLString) else {
            throw NetworkError.invalidURL
        }

        if !endpoint.path.isEmpty {
            let path = endpoint.path.hasPrefix("/") ? endpoint.path : "/" + endpoint.path
            components.path += path
        }

        let queryItems = endpoint.api.defaultQueryItems + endpoint.queryItems
        if !queryItems.isEmpty {
            components.queryItems = queryItems
        }

        guard let url = components.url else {
            throw NetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = endpoint.method.rawValue
        request.httpBody = endpoint.body

        let headers = endpoint.api.defaultHeaders
            .merging(endpoint.headers) { _, endpointValue in endpointValue }
        for (field, value) in headers {
            request.setValue(value, forHTTPHeaderField: field)
        }

        return request
    }
}
