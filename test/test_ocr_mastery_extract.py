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
