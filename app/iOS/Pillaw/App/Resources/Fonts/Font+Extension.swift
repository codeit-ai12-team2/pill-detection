//
//  Font+Extension.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//
import SwiftUI

extension Font {
    /// 구름소파 남김체. 이름은 ttf의 PostScript 이름(파일 이름과 다름).
    /// relativeTo 기준으로 Dynamic Type 크기에 맞춰 함께 스케일된다.
    static func cloudSofa(size: CGFloat, relativeTo textStyle: TextStyle = .body) -> Font {
        .custom("Cloudsofa_namgim-Regular", size: size, relativeTo: textStyle)
    }

    /// 그리운 몽토리체
    static func griunMongtori(size: CGFloat, relativeTo textStyle: TextStyle = .body) -> Font {
        .custom("Griun_Mongtori-Rg", size: size, relativeTo: textStyle)
    }
}
