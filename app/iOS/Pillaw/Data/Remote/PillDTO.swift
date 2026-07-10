//
//  PillDTO.swift
//  Pillaw
//
//  Created by Yuventius Choi on 7/8/26.
//

import Foundation

/// 낱알식별 API 응답의 item 한 건.
nonisolated struct PillDTO: Decodable {
    let itemSeq: String
    let itemName: String
    let entpSeq: String?
    let entpName: String?
    let chart: String?
    let itemImage: String?
    let printFront: String?
    let printBack: String?
    let drugShape: String?
    let colorClass1: String?
    let colorClass2: String?
    let lineFront: String?
    let lineBack: String?
    let lengLong: String?
    let lengShort: String?
    let thick: String?
    let imgRegistTs: String?
    let classNo: String?
    let className: String?
    let etcOtcName: String?
    let itemPermitDate: String?
    let formCodeName: String?
    let markCodeFrontAnal: String?
    let markCodeBackAnal: String?
    let markCodeFrontImg: String?
    let markCodeBackImg: String?
    let itemEngName: String?
    let changeDate: String?
    let markCodeFront: String?
    let markCodeBack: String?
    let ediCode: String?
    let bizrno: String?
    let stdCd: String?

    private enum CodingKeys: String, CodingKey {
        case itemSeq = "ITEM_SEQ"
        case itemName = "ITEM_NAME"
        case entpSeq = "ENTP_SEQ"
        case entpName = "ENTP_NAME"
        case chart = "CHART"
        case itemImage = "ITEM_IMAGE"
        case printFront = "PRINT_FRONT"
        case printBack = "PRINT_BACK"
        case drugShape = "DRUG_SHAPE"
        case colorClass1 = "COLOR_CLASS1"
        case colorClass2 = "COLOR_CLASS2"
        case lineFront = "LINE_FRONT"
        case lineBack = "LINE_BACK"
        case lengLong = "LENG_LONG"
        case lengShort = "LENG_SHORT"
        case thick = "THICK"
        case imgRegistTs = "IMG_REGIST_TS"
        case classNo = "CLASS_NO"
        case className = "CLASS_NAME"
        case etcOtcName = "ETC_OTC_NAME"
        case itemPermitDate = "ITEM_PERMIT_DATE"
        case formCodeName = "FORM_CODE_NAME"
        case markCodeFrontAnal = "MARK_CODE_FRONT_ANAL"
        case markCodeBackAnal = "MARK_CODE_BACK_ANAL"
        case markCodeFrontImg = "MARK_CODE_FRONT_IMG"
        case markCodeBackImg = "MARK_CODE_BACK_IMG"
        case itemEngName = "ITEM_ENG_NAME"
        case changeDate = "CHANGE_DATE"
        case markCodeFront = "MARK_CODE_FRONT"
        case markCodeBack = "MARK_CODE_BACK"
        case ediCode = "EDI_CODE"
        case bizrno = "BIZRNO"
        case stdCd = "STD_CD"
    }
}
