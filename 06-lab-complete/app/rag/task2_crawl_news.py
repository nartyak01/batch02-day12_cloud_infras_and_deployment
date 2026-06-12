"""
Task 2 — Crawl bài báo về nghệ sĩ liên quan tới ma tuý.

Dùng requests (không Playwright) để tránh lỗi pipe cleanup trên Windows.
Crawl4AI vẫn có thể bật qua USE_CRAWL4AI=true nếu cần.
"""

import json
import os
import re
from datetime import datetime
from html import unescape
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://vnexpress.net/ca-si-chu-bin-bi-tam-giu-vi-lien-quan-ma-tuy-4755275.html",
    "https://ngoisao.vnexpress.net/chi-dan-va-andrea-aybar-bi-khoi-to-vi-to-chuc-su-dung-ma-tuy-4815983.html",
    "https://vnexpress.net/anh-em-ca-si-chi-dan-ru-nhieu-nguoi-choi-ma-tuy-nhu-the-nao-4929804.html",
    "https://vnexpress.net/ca-si-long-nhat-son-ngoc-minh-bi-bat-vi-lien-quan-ma-tuy-5060857.html",
    "https://thanhnien.vn/tu-hinh-hoai-dj-trong-duong-day-108-kg-ma-tuy-nuoc-vui-185260507151056936.htm",
]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
}

USE_CRAWL4AI = os.getenv("USE_CRAWL4AI", "").lower() in ("1", "true", "yes")


def setup_directory():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _html_to_text(html_fragment: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html_fragment, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(re.sub(r"\s+", " ", text).strip())
    return text


def _extract_title(html: str) -> str:
    for pattern in (
        r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
        r"<title>([^<]+)</title>",
        r"<h1[^>]*class=\"[^\"]*title[^\"]*\"[^>]*>([^<]+)</h1>",
    ):
        match = re.search(pattern, html, re.I)
        if match:
            return unescape(match.group(1).strip())
    return "Unknown"


def _extract_article_body(html: str) -> str:
    patterns = [
        r'class="fck_detail"[^>]*>(.*?)</(?:article|div)>',
        r'class="[^"]*detail-content[^"]*"[^>]*>(.*?)</(?:article|div)>',
        r"<article[^>]*>(.*?)</article>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.S | re.I)
        if match:
            text = _html_to_text(match.group(1))
            if len(text) >= 200:
                return text
    return _html_to_text(html)


def crawl_article(url: str) -> dict:
    """Crawl một bài báo bằng requests."""
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    html = resp.text

    title = _extract_title(html)
    content = _extract_article_body(html)
    if len(content) < 200:
        raise ValueError(f"Noi dung qua ngan ({len(content)} chars)")

    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content[:8000],
    }


async def _crawl_article_crawl4ai(url: str, crawler) -> dict:
    """Optional Crawl4AI path — dùng chung một crawler instance."""
    result = await crawler.arun(url=url)
    content = getattr(result, "markdown", "") or ""
    if len(content) < 200:
        raise ValueError("Insufficient content from crawl4ai")
    meta = getattr(result, "metadata", {}) or {}
    return {
        "url": url,
        "title": meta.get("title", "Unknown"),
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content[:8000],
    }


async def _crawl_all_crawl4ai():
    """Crawl4AI: một browser cho tất cả URL, đóng gọn trong async with."""
    import asyncio

    from crawl4ai import AsyncWebCrawler

    setup_directory()
    saved = 0

    async with AsyncWebCrawler() as crawler:
        for i, url in enumerate(ARTICLE_URLS, 1):
            print(f"[{i}/{len(ARTICLE_URLS)}] Crawling (crawl4ai): {url}")
            try:
                article = await _crawl_article_crawl4ai(url, crawler)
            except Exception:
                article = crawl_article(url)
                print("  -> fallback requests")

            filepath = DATA_DIR / f"article_{i:02d}.json"
            filepath.write_text(
                json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"  [OK] Saved: {filepath.name} ({len(article['content_markdown'])} chars)")
            saved += 1

    await asyncio.sleep(0.25)
    print(f"\n[OK] Total articles saved: {saved}")


def crawl_all():
    """Crawl all URLs from ARTICLE_URLS."""
    if USE_CRAWL4AI:
        import asyncio

        asyncio.run(_crawl_all_crawl4ai())
        return

    setup_directory()
    saved = 0

    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        try:
            article = crawl_article(url)
        except Exception as exc:
            print(f"  [ERR] Crawl failed: {exc}")
            raise RuntimeError(f"Khong crawl duoc bai {i}: {url}") from exc

        filepath = DATA_DIR / f"article_{i:02d}.json"
        filepath.write_text(
            json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [OK] Saved: {filepath.name} ({len(article['content_markdown'])} chars)")
        saved += 1

    print(f"\n[OK] Total articles saved: {saved}")


if __name__ == "__main__":
    crawl_all()
