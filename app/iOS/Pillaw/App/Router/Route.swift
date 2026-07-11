//
//  Route.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//
import Foundation

nonisolated enum Route: Hashable {
    case camera
    case realTimeCamera
    case pillInfo(id: String)
    case pillInfoBanned
    case favorite
}
