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


def test_extract_drawer_skips_single_char_label_fragment():
    """「绑制」被拆成单独「制」时跳过，仍读取下一行画师名。"""
    text = "绘制\n制\nLoWro\n专精\n情报"
    assert extract_drawer(text) == "LoWro"


def test_extract_drawer_after_fragment_does_not_read_further_lines():
    """「制」后只试紧邻一行；无 LoWro 时不吃 009。"""
    text = "绘制\n制\n009\nROanG\n专精\nx"
    assert extract_drawer(text) is None


def test_extract_drawer_draw_fragment_then_artist_like_taraxa():
    """风絮：绘 + •二开，无顿号故只读一行；• 与 - 同样剥除；不收 *。"""
    text = "绘\n\u2022二开\n*\n专精\n草药"
    assert extract_drawer(text) == "二开"
    assert "•" not in (extract_drawer(text) or "")


def test_extract_drawer_ju_like_ocr_block():
    """矩：绘 + ·虬墨一型，无顿号只读一行；· 剥除；不收 *。"""
    text = "绘\n\u00b7虬墨一型\n*\n专精\n机械制造"
    assert extract_drawer(text) == "虬墨一型"
    assert "*" not in (extract_drawer(text) or "")
    assert "·" not in (extract_drawer(text) or "")


def test_extract_drawer_belone_like_ocr_block():
    text = """
P
制
LoWro
009
ROanG
专精
情报
"""
    assert extract_drawer(text) == "LoWro"


def test_extract_drawer_weak_label_fragment_then_name():
    """无完整「绘制」时，单行「制」作弱锚点并打日志。"""
    msgs: list[str] = []

    def warn(msg: str, *args: object) -> None:
        msgs.append(msg % args if args else msg)

    text = "制\nLoWro\n专精\n情报"
    assert extract_drawer(text, warn=warn) == "LoWro"
    assert any("weak_label" in m for m in msgs)


def test_extract_drawer_rejects_single_char_artist_name():
    """单字画师名（含 *）不再二次放宽采集，避免误收 OCR 噪点。"""
    msgs: list[str] = []

    def warn(msg: str, *args: object) -> None:
        msgs.append(msg % args if args else msg)

    text = "绘制\nK\n专精\nxxx"
    assert extract_drawer(text, warn=warn) is None


def test_label_fragment_never_becomes_drawer_name():
    msgs: list[str] = []

    def warn(msg: str, *args: object) -> None:
        msgs.append(msg % args if args else msg)

    assert extract_drawer("制\n专精\nx", warn=warn) is None
    assert not any("制" in m and "name=制" in m for m in msgs)


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
