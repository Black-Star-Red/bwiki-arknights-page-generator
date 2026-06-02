"""画师 OCR 文本解析（无 Paddle）。"""

from shared.ocr_profile_fields import extract_drawer, format_drawer_string


def test_format_drawer_string():
    assert (
        format_drawer_string(["Studio Montagne"], ["Skade"])
        == "Studio Montagne、Skade（原案）"
    )
    assert format_drawer_string(["A", "B"], []) == "A、B"
    assert format_drawer_string([], ["C"]) == "C（原案）"


def test_extract_drawer_from_merged_text():
    text = """
    专精：xxx、yyy
    绘制：Studio Montagne
    原案：Skade
    身高：150cm
    """
    assert extract_drawer(text) == "Studio Montagne、Skade（原案）"


def test_extract_drawer_inline_colon():
    text = "绘制: Foo、Bar\n原案: Baz"
    assert extract_drawer(text) == "Foo、Bar、Baz（原案）"


def test_extract_drawer_multiline_labels_like_ocr():
    """官号预告 OCR：绘制/原案 独占一行，画师名在下一行。"""
    text = """
服装设计、裁缝、
文书工作、射击（弓）
绘制
StudioMontagne
原案
Skade
"""
    assert extract_drawer(text) == "StudioMontagne、Skade（原案）"


def test_extract_drawer_leading_dash_on_name():
    text = "绘制\n-StudioMontagne\n专精\n调查情报"
    assert extract_drawer(text) == "StudioMontagne"


def test_extract_drawer_designer_ocr_typo_line():
    text = "绘制\nStudioMontagne\n原案\n-m9nokuro\n专精"
    assert extract_drawer(text) == "StudioMontagne、m9nokuro（原案）"


def test_extract_drawer_stops_before_skill_text_without_designer():
    """无原案时绘制后紧跟特性文案，不应吞进画师。"""
    text = """
可以在攻击范围内选择一次战术点来召唤
绘制
-StudioMontagne
援军，自身攻击援军阻挡的敌人时攻击力
提升至150%；不受部署数量限制，但再
部署时间极长
第一天赋
"""
    assert extract_drawer(text) == "StudioMontagne"
