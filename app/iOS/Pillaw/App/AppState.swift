//
//  AppState.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/7/26.
//
import Foundation
import Observation

@Observable
final class AppState {
    enum Root {
        case splash
        case home
    }
    
    var root: Root = .splash
}
