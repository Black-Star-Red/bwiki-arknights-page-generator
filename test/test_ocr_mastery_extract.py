"""专精 OCR 文本解析（无 Paddle）。"""

from shared.ocr_profile_fields import extract_mastery


def test_extract_mastery_inline_multi():
    text = "专精：服装设计、裁缝、文书工作"
    assert extract_mastery(text) == "服装设计、裁缝、文书工作"


def test_extract_mastery_ju_ocr_block():
    """矩：画师区 ·、 噪点不能起锚；专精后只取机械制造。"""
    text = "绘\n\u00b7虬墨一型\n*\n\u00b7、\n专精\n机械制造\n身高"
    assert extract_mastery(text) == "机械制造"
    assert "·" not in (extract_mastery(text) or "")


def test_extract_mastery_ju_dotted_label_line():
    """终端 OCR：·专精· 换行 机械制造。"""
    text = "绘\n\u00b7虬墨一型\n\u00b7\u4e13\u7cbe\u00b7\n机械制造"
    assert extract_mastery(text) == "机械制造"


def test_extract_mastery_wind_taraxa_like():
    text = "绘\n\u2022二开\n专精\n草药学、\n护理学、载具驾驶"
    assert extract_mastery(text) == "草药学、护理学、载具驾驶"


def test_extract_mastery_chen_strips_leading_junk():
    text = "专精：\u00b7剑法、战场指挥、情报战"
    assert extract_mastery(text) == "剑法、战场指挥、情报战"


def test_extract_mastery_ignores_orphan_dun_line():
    """无「专精」标签的 ·、 行不得单独成专精。"""
    text = "\u00b7、\n绘制\nStudio\n专精\n全领域工程"
    assert extract_mastery(text) == "全领域工程"

def test_extract_mastery_plus_wrapped_label_line():
    """「专精」标签行首 + 后接标签的 “+” 时，正常解析。"""
    text = "+专精+\n应用源石学、\n信息与计算科学"
    assert extract_mastery(text) == "应用源石学、信息与计算科学"

def test_extract_mastery_value_before_label_mechanist():
    """机械师预告图：OCR 先输出专精前半段，再出「专精」标签。"""
    text = (
        "哥伦比亚\n出身\n机械工程、电气工程\n专精\n化学工程、过量劳动\n"
        "绘制\nStudioMontagne\n原案\nCenm0"
    )
    assert extract_mastery(text) == "机械工程、电气工程、化学工程、过量劳动"
    
def test_extract_mastery_value_before_label_does_not_eat_drawer():
    text = "绘\n\u2022二开\n专精\n草药学、护理学"
    assert extract_mastery(text) == "草药学、护理学"