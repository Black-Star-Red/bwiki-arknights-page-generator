"""限定专栏：活动时间月日 + publish_time 年份。"""

from datetime import datetime

from shared.utils.format_date import CN_TZ, zh_ymd_from_pool_article


def test_side_story_sample_md_with_publish_time():
    summary = (
        "[图片] 活动时间：05月01日 12:00 - 05月15日 03:59 活动说明：活动期间【限定寻访·庆典】"
    )
    ltime = summary.find("活动时间：")
    rtime = summary.find("日")
    md = summary[ltime + 5 : rtime + 1]
    pub = int(datetime(2026, 3, 20, 10, 0, 0, tzinfo=CN_TZ).timestamp())
    assert zh_ymd_from_pool_article(pub, md) == "2026年5月1日"
