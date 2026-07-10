//
//  Pill.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Foundation
import SwiftData

@Model
final class Pill {
    /// 낱알식별 API의 품목일련번호. 중복 저장 방지를 위해 unique.
    @Attribute(.unique) var itemSeq: String
    var itemName: String

    /// 정보 상태 (정상 / 정보를 찾을 수 없음 / 복용 금지)
    var status: PillStatus = PillStatus.normal

    /// 즐겨찾기 여부
    var isFavorite: Bool = false

    /// 즐겨찾기한 시각 (즐겨찾기 목록 정렬용)
    var favoritedAt: Date?

    // class_mapping.csv (YOLO 클래스 매핑) 정보
    var classIndex: Int
    var dlName: String
    var categoryId: String

    // 낱알식별 API 응답 정보
    var entpSeq: String?
    var entpName: String?
    var chart: String?
    var itemImage: String?
    var printFront: String?
    var printBack: String?
    var drugShape: String?
    var colorClass1: String?
    var colorClass2: String?
    var lineFront: String?
    var lineBack: String?
    var lengLong: String?
    var lengShort: String?
    var thick: String?
    var imgRegistTs: String?
    var classNo: String?
    var className: String?
    var etcOtcName: String?
    var itemPermitDate: String?
    var formCodeName: String?
    var markCodeFrontAnal: String?
    var markCodeBackAnal: String?
    var markCodeFrontImg: String?
    var markCodeBackImg: String?
    var itemEngName: String?
    var changeDate: String?
    var markCodeFront: String?
    var markCodeBack: String?
    var ediCode: String?
    var bizrno: String?
    var stdCd: String?
    
    init() {
        itemSeq = "198700706"
        itemName = "보령부스파정"
        classIndex = 0
        dlName = "보령부스파정"
        categoryId = "1900"
    }

    init(dto: PillDTO, mapping: ClassMapping) {
        itemSeq = dto.itemSeq
        itemName = dto.itemName
        status = .normal
        classIndex = mapping.classIndex
        dlName = mapping.dlName
        categoryId = mapping.categoryId
        entpSeq = dto.entpSeq
        entpName = dto.entpName
        chart = dto.chart
        itemImage = dto.itemImage
        printFront = dto.printFront
        printBack = dto.printBack
        drugShape = dto.drugShape
        colorClass1 = dto.colorClass1
        colorClass2 = dto.colorClass2
        lineFront = dto.lineFront
        lineBack = dto.lineBack
        lengLong = dto.lengLong
        lengShort = dto.lengShort
        thick = dto.thick
        imgRegistTs = dto.imgRegistTs
        classNo = dto.classNo
        className = dto.className
        etcOtcName = dto.etcOtcName
        itemPermitDate = dto.itemPermitDate
        formCodeName = dto.formCodeName
        markCodeFrontAnal = dto.markCodeFrontAnal
        markCodeBackAnal = dto.markCodeBackAnal
        markCodeFrontImg = dto.markCodeFrontImg
        markCodeBackImg = dto.markCodeBackImg
        itemEngName = dto.itemEngName
        changeDate = dto.changeDate
        markCodeFront = dto.markCodeFront
        markCodeBack = dto.markCodeBack
        ediCode = dto.ediCode
        bizrno = dto.bizrno
        stdCd = dto.stdCd
    }

    /// API 조회가 불가능한 알약을 CSV 정보만으로 저장할 때 사용한다.
    init(mapping: ClassMapping, status: PillStatus) {
        itemSeq = mapping.itemSeq
        itemName = mapping.dlName
        self.status = status
        classIndex = mapping.classIndex
        dlName = mapping.dlName
        categoryId = mapping.categoryId
    }

    /// 즐겨찾기를 토글한다. SwiftData가 자동 저장하므로 호출부에서 따로 save할 필요 없다.
    func toggleFavorite() {
        isFavorite.toggle()
        favoritedAt = isFavorite ? .now : nil
    }
}
