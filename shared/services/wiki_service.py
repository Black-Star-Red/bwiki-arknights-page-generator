"""Wiki related service helpers."""

from __future__ import annotations

import io
from typing import Any


def write_site_page(
    site: Any,
    page_name: str,
    page_content: str,
    *,
    wiki_use_test_page: bool = True,
    errors_module: Any,
) -> None:
    """Write content to wiki page (sandbox or real page)."""
    if wiki_use_test_page:
        page = site.pages[f"用户:{site.username}/测试页"]
    else:
        page = site.pages[page_name]
    try:
        result = page.edit(text=page_content, summary=f"{page_name}")
        print(result)
    except errors_module.APIError as e:
        if e.code == "abusefilter-warning":
            print("触发了防滥用过滤器警告，正在尝试二次提交...")
            if wiki_use_test_page:
                result = page.edit(text=page_content, summary=f"{page_name}")
            else:
                result = page.edit(text=page_content)
            print(result)
        else:
            raise


def upload_site_file_with_retry(site: Any, file_obj: Any, filename: str) -> Any:
    """
    Upload a file and retry once when wiki returns Warning.
    """
    upload_result = site.upload(file_obj, filename=filename)
    if upload_result.get("result") == "Warning":
        print(upload_result)
        print("再次尝试")
        upload_result = site.upload(file_obj, filename=filename)
    print("上传结果:", upload_result)
    return upload_result


def publish_wiki_page_if_enabled(
    *,
    enabled: bool,
    get_site_fn: Any,
    create_site_page_fn: Any,
    page_name: str,
    page_content: str,
    wiki_use_test_page: bool,
    offline_message: str,
) -> None:
    """Create a wiki page when enabled, with shared offline handling."""
    if not enabled:
        return
    site_obj = get_site_fn()
    if site_obj is not None:
        create_site_page_fn(site_obj, page_name, page_content, wiki_use_test_page)
    else:
        print(offline_message)


def upload_operator_portrait_if_enabled(
    *,
    enabled: bool,
    requests_module: Any,
    get_site_fn: Any,
    upload_fn: Any,
    operator_id: str,
    operator_name: str,
    headers: dict,
) -> None:
    """Fetch and upload operator portrait when enabled."""
    portrait_resp = requests_module.get(
        f"https://web.hycdn.cn/arknights/game/assets/char/portrait/{operator_id}.png",
        headers=headers,
    )
    if portrait_resp.status_code == 200:
        site_obj = get_site_fn()
        if site_obj is not None:
            if enabled:
                file_obj = io.BytesIO(portrait_resp.content)
                upload_fn(site_obj, file_obj, f"{operator_name}06.png")
        else:
            print("site创建失败")
    else:
        print(f"干员{operator_name}半身像,获取失败")


__all__ = [
    "write_site_page",
    "upload_site_file_with_retry",
    "publish_wiki_page_if_enabled",
    "upload_operator_portrait_if_enabled",
]
