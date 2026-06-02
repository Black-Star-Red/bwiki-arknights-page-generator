"""Wiki 写入与交互确认。"""

from __future__ import annotations

from typing import Callable

from mwclient import errors

from shared.services import write_site_page


def wiki_yes_no(
    prompt: str,
    *,
    wiki_key: str,
    wiki_flags: dict | None,
    interactive: bool,
    wiki_confirm: Callable[[str, str], bool] | None = None,
) -> bool:
    """
    Wiki 步骤确认：
    - interactive=True：终端 input(Y/N)。
    - interactive=False：先要求 wiki_flags[wiki_key] 为真；若提供 wiki_confirm，再二次回调（如 GUI 弹窗）。
    """
    if interactive:
        try:
            return input(prompt) == "Y"
        except EOFError:
            return False
    if not (wiki_flags and wiki_flags.get(wiki_key)):
        return False
    if wiki_confirm is not None:
        return bool(wiki_confirm(prompt, wiki_key))
    return True


def create_site_page(site, page_name, page_content, wiki_use_test_page: bool = True):
    """写入 Wiki 页面。wiki_use_test_page 为真时写入当前用户沙盒页，避免误改正式词条。"""
    write_site_page(
        site,
        page_name,
        page_content,
        wiki_use_test_page=wiki_use_test_page,
        errors_module=errors,
    )
