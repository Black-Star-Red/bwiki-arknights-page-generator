"""HTTP header builders for external requests."""

from __future__ import annotations


def build_bilibili_headers(cookies: str) -> dict[str, str]:
    """Build headers for bilibili API calls."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Cookie": cookies,
    }


def build_wiki_headers() -> dict[str, str]:
    """Build headers for wiki site session."""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://wiki.biligame.com/arknights/",
    }


__all__ = ["build_bilibili_headers", "build_wiki_headers"]
