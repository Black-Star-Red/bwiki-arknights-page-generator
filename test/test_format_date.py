"""中文实装日期格式化。"""

from datetime import datetime, timezone

from shared.utils.format_date import (
    CN_TZ,
    format_ts_cn_datetime,
    format_zh_ymd,
    normalize_supplementary_release_date,
    normalize_zh_release_date,
    zh_ymd_from_pool_article,
    zh_ymd_from_unix_ts,
)


def test_format_zh_ymd_no_leading_zero():
    assert format_zh_ymd(2026, 6, 2) == "2026年6月2日"


def test_normalize_full_ymd():
    assert normalize_zh_release_date("2026年06月02日") == "2026年6月2日"
    assert normalize_zh_release_date("2026年6月2日") == "2026年6月2日"


def test_normalize_month_day_only():
    assert normalize_zh_release_date("05月01日") == "5月1日"
    assert normalize_zh_release_date("5月1日") == "5月1日"


def test_normalize_inside_wiki_link():
    raw = (
        "[https://t.bilibili.com/1167248656573661220?spm_id_from=333.1387.0.0 "
        "2026年06月02日]"
    )
    assert "2026年6月2日" in normalize_zh_release_date(raw)
    assert "06月" not in normalize_zh_release_date(raw)


def test_normalize_passthrough_non_date():
    assert normalize_zh_release_date("") == ""
    assert normalize_zh_release_date("x") == "x"


def test_zh_ymd_from_unix_ts_uses_shanghai_calendar():
    # 2026-05-31 23:00:00 UTC = 2026-06-01 07:00 北京时间（泡影苍霆类开服日）
    ts = int(datetime(2026, 5, 31, 23, 0, 0, tzinfo=timezone.utc).timestamp())
    assert zh_ymd_from_unix_ts(ts) == "2026年6月1日"
    assert format_ts_cn_datetime(ts) == "2026-06-01 07:00:00"


def test_zh_ymd_from_pool_article_publish_year():
    pub = int(datetime(2026, 4, 28, 12, 0, 0, tzinfo=CN_TZ).timestamp())
    assert zh_ymd_from_pool_article(pub, "05月01日") == "2026年5月1日"
    assert zh_ymd_from_pool_article(pub, "05月01日 12:00") == "2026年5月1日"


def test_zh_ymd_from_pool_article_no_publish_ts():
    assert zh_ymd_from_pool_article(None, "05月01日") == "5月1日"


def test_normalize_supplementary_release_date_wiki_link():
    raw = (
        "[https://t.bilibili.com/1207696702209785874?spm_id_from=333.1387.0.0 "
        "2026年06月02日]"
    )
    out = normalize_supplementary_release_date(raw)
    assert "2026年6月2日" in out
    assert "06月" not in out
