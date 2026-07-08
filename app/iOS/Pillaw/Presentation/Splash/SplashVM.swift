//
//  SplashVM.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Foundation
import Observation
import SwiftData
import os

private let logger = Logger(
    subsystem: Bundle.main.bundleIdentifier ?? "Pillaw",
    category: "Seeding"
)

@Observable
final class SplashVM {
    enum Phase {
        case checking
        case seeding(done: Int, total: Int)
        case finished
        case failed(message: String)
    }

    private let pillRepo: PillRepo
    private let classMappingCSV: String

    var phase: Phase = .checking

    var isFinished: Bool {
        if case .finished = phase { return true }
        return false
    }

    init(pillRepo: PillRepo, classMappingCSV: String) {
        self.pillRepo = pillRepo
        self.classMappingCSV = classMappingCSV
    }

    /// 저장된 알약 데이터가 없으면 class_mapping.csv의 item_seq들로
    /// API를 호출해 SwiftData에 저장한다. 이미 저장된 항목은 건너뛰므로
    /// 중간에 실패해도 다음 실행에서 나머지만 이어서 받는다.
    func seedIfNeeded(context: ModelContext) async {
        let mappings = ClassMapping.parse(csv: classMappingCSV)
        guard !mappings.isEmpty else {
            logger.error("class_mapping CSV가 비어 있거나 파싱에 실패함")
            phase = .failed(message: "데이터 준비에 실패했어요.")
            return
        }

        do {
            let saved = Set(try context.fetch(FetchDescriptor<Pill>()).map(\.itemSeq))
            let targets = mappings.filter { !saved.contains($0.itemSeq) }

            guard !targets.isEmpty else {
                phase = .finished
                return
            }

            let total = targets.count
            var done = 0
            var failedSeqs: [String] = []
            phase = .seeding(done: 0, total: total)
            logger.info("시딩 시작: \(total)건")

            // API에서 조회되지 않는 알약은 지정된 상태로 CSV 정보만 저장한다.
            for mapping in targets {
                guard let status = PillStatus.overrides[mapping.itemSeq] else { continue }
                context.insert(Pill(mapping: mapping, status: status))
                done += 1
                phase = .seeding(done: done, total: total)
                logger.info("상태 지정 저장 item_seq=\(mapping.itemSeq, privacy: .public) (\(mapping.dlName, privacy: .public)): \(status.rawValue, privacy: .public)")
            }
            let fetchTargets = targets.filter { PillStatus.overrides[$0.itemSeq] == nil }

            let repo = pillRepo
            await withTaskGroup(of: (ClassMapping, PillDTO?).self) { group in
                var iterator = fetchTargets.makeIterator()

                func addFetchTask(_ mapping: ClassMapping) {
                    group.addTask {
                        do {
                            guard let dto = try await repo.fetchPill(itemSeq: mapping.itemSeq) else {
                                await logger.error("결과 없음 item_seq=\(mapping.itemSeq, privacy: .public) (\(mapping.dlName, privacy: .public))")
                                return (mapping, nil)
                            }
                            return (mapping, dto)
                        } catch {
                            await logger.error("요청 실패 item_seq=\(mapping.itemSeq, privacy: .public) (\(mapping.dlName, privacy: .public)): \(String(describing: error), privacy: .public)")
                            return (mapping, nil)
                        }
                    }
                }

                // 공공 API 부하를 고려해 동시 요청은 5개로 제한
                for _ in 0..<5 {
                    guard let mapping = iterator.next() else { break }
                    addFetchTask(mapping)
                }

                for await (mapping, dto) in group {
                    if let dto {
                        context.insert(Pill(dto: dto, mapping: mapping))
                    } else {
                        failedSeqs.append(mapping.itemSeq)
                    }
                    done += 1
                    phase = .seeding(done: done, total: total)

                    if let next = iterator.next() {
                        addFetchTask(next)
                    }
                }
            }

            try context.save()

            if failedSeqs.isEmpty {
                logger.info("시딩 완료: \(total)건")
                phase = .finished
            } else {
                logger.error("시딩 미완료 — 실패 \(failedSeqs.count)건: \(failedSeqs.joined(separator: ", "), privacy: .public)")
                let savedCount = try context.fetchCount(FetchDescriptor<Pill>())
                phase = .failed(
                    message: "일부 데이터를 받지 못했어요. (\(savedCount)/\(mappings.count))"
                )
            }
        } catch {
            logger.error("시딩 실패: \(String(describing: error), privacy: .public)")
            phase = .failed(message: "데이터 준비에 실패했어요.")
        }
    }
}
