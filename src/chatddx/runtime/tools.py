import re
from html import unescape
from urllib.parse import parse_qs, urlparse

import httpx
from pydantic_ai import RunContext

from chatddx.runtime.context import AgentContext

_WEB_SEARCH_URL = "https://html.duckduckgo.com/html/"
_RESULT_RE = re.compile(
    r'class="result__a"[^>]*href="(?P<href>[^"]+)"[^>]*>(?P<title>.*?)</a>'
    r".*?"
    r'class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
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


def web_search(
    _: RunContext[AgentContext], query: str, max_results: int = 5
) -> str:
    """Search the web and return the top results (title, url, snippet).

    Use this to look up current facts, documentation, or anything you're not
    confident about from memory, instead of guessing.
    """
    response = httpx.get(
        _WEB_SEARCH_URL,
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; chatddx-web-search/1.0)"},
        timeout=10.0,
        follow_redirects=True,
    )
    response.raise_for_status()

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


def sentinel_string(_: RunContext[AgentContext]) -> str:
    """This is tool returns a string that is hard to know in advance"""
    return "asdf"


def sentinel_op(_: RunContext[AgentContext], v1: int, v2: int) -> float:
    """This tool takes two arguments and performs an operation on them"""
    return v1 % v2


def user_details(_: RunContext[AgentContext]) -> str:
    """Run this function to get user's name"""
    return "pelle"


def is_prime(_: RunContext[AgentContext], x: int) -> bool:
    """Takes an integer x and returns True if it's a prime and False otherwise"""
    return x == 15
