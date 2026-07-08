//
//  HomeVM.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//

import Foundation
import Observation
import SwiftData
import os

private let logger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "Pillaw",
    category: "HomeVM"
)

@Observable
final class HomeVM {
    var pills: [Pill] = []
    
    func loadPills(context: ModelContext) async {
        do {
            pills = try context.fetch(FetchDescriptor<Pill>())
        } catch {
            logger.error("데이터 로드 실패")
        }
    }
}
