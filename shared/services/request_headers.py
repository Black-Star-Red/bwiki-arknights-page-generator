"""HTTP header builders for external requests."""

from __future__ import annotations


def build_bilibili_headers(cookies: str, *, mid: str | None = None) -> dict[str, str]:
    """Build headers for bilibili API calls."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        # 不含 br：未安装 brotli 时 requests 可能得到空 body，导致 JSON 解析失败
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Cookie": cookies,
    }
    if mid:
        headers["Referer"] = f"https://space.bilibili.com/{mid}/dynamic"
        headers["Origin"] = "https://space.bilibili.com"
    return headers


def build_hycdn_portrait_headers() -> dict[str, str]:
    """鹰角 hycdn 半身像；勿用 B 站 Cookie/Referer（会 403）。"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Referer": "https://ak.hypergryph.com/",
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


__all__ = ["build_bilibili_headers", "build_hycdn_portrait_headers", "build_wiki_headers"]
