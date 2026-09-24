"""The top results of a DuckDuckGo search: the title, url and snippet of each."""

import re
from html import unescape
from urllib.parse import parse_qs, urlparse

import httpx2

_WEB_SEARCH_URL = "https://html.duckduckgo.com/html/"
_RESULT_RE = re.compile(
    r'class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    + r".*?"
    + r'class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    +re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean_html(fragment: str) -> str:
    return unescape(_TAG_RE.sub("", fragment)).strip()


def _resolve_result_url(href: str) -> str:
    """DuckDuckGo's HTML results link through a `/l/?uddg=...` redirect; unwrap it."""
    if href.startswith("//"):
        href = f"https:{href}"

    parsed = urlparse(href)
    if parsed.netloc.endswith("duckduckgo.com") and parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg")
        if target:
            return target[0]

    return href


def web_search(query: str, max_results: int = 5) -> str:
    response = httpx2.get(
        _WEB_SEARCH_URL,
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; chatddx-web-search/1.0)"},
        timeout=10.0,
        follow_redirects=True,
    )
    _ = response.raise_for_status()

    results: list[str] = []
    for match in _RESULT_RE.finditer(response.text):
        title = _clean_html(match.group("title"))
        url = _resolve_result_url(match.group("href"))
        snippet = _clean_html(match.group("snippet"))
        results.append(f"{len(results) + 1}. {title}\n   {url}\n   {snippet}")

        if len(results) >= max_results:
            break

    if not results:
        return f"No results found for '{query}'."

    return "\n".join(results)
