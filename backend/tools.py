"""
Tools for the Research Assistant Agent.

Each tool is a plain Python function. The agent discovers them via a description
string that is injected into the system prompt.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Shared HTTP client helpers
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; ResearchAssistantAgent/1.0; "
        "+https://github.com/example/research-agent)"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _get_client(timeout: float = 15.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout,
        follow_redirects=True,
        headers=_DEFAULT_HEADERS,
    )


# ---------------------------------------------------------------------------
# Web search (DuckDuckGo HTML – no API key required)
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 6) -> str:
    """
    Search the web and return a list of titles, URLs and short snippets.
    Example: web_search: latest advances in CRISPR gene editing 2024
    """
    query = query.strip()
    if not query:
        return "Error: empty search query"

    max_results = max(1, min(max_results, 10))
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        with _get_client() as client:
            r = client.get(url)
            r.raise_for_status()
    except Exception as e:
        return f"Error performing web search: {e}"

    soup = BeautifulSoup(r.text, "html.parser")
    results = []

    # DuckDuckGo HTML result blocks
    for result in soup.select("div.result, div.web-result"):
        if len(results) >= max_results:
            break

        title_el = result.select_one("a.result__a")
        snippet_el = result.select_one("a.result__snippet, div.result__snippet")
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        href = title_el.get("href") or ""
        # DDG sometimes wraps the real URL
        if "uddg=" in href:
            from urllib.parse import parse_qs, urlparse as up

            qs = parse_qs(up(href).query)
            href = qs.get("uddg", [href])[0]

        snippet = ""
        if snippet_el:
            snippet = snippet_el.get_text(" ", strip=True)
            if len(snippet) > 280:
                snippet = snippet[:280].rsplit(" ", 1)[0] + "…"

        if title and href and href.startswith("http"):
            results.append(
                f"{len(results)+1}. {title}\n"
                f"   URL: {href}\n"
                f"   Snippet: {snippet or '(no snippet)'}"
            )

    if not results:
        return (
            f"No web results found for '{query}'. "
            "Try a different query or use the wikipedia tool."
        )

    header = f"Web search results for '{query}' ({len(results)} hits):\n"
    return header + "\n\n".join(results)


# ---------------------------------------------------------------------------
# Fetch & extract readable text from a URL
# ---------------------------------------------------------------------------

def browse_url(url: str) -> str:
    """
    Fetch a web page and return its main textual content (title + body).
    Truncated to keep context manageable. Use after web_search to dig deeper.
    Example: browse_url: https://en.wikipedia.org/wiki/CRISPR
    """
    url = url.strip()
    if not url:
        return "Error: empty URL"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        with _get_client(timeout=20.0) as client:
            r = client.get(url)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return f"Error: URL does not appear to be HTML/text (content-type: {content_type})"
            html = r.text
    except Exception as e:
        return f"Error fetching URL '{url}': {e}"

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Prefer <article> or main content areas
    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find("div", class_=re.compile(r"(content|article|post|entry)", re.I))
        or soup.body
        or soup
    )

    # Collect paragraphs and headings
    texts = []
    for el in main.find_all(["h1", "h2", "h3", "p", "li"]):
        t = el.get_text(" ", strip=True)
        if t and len(t) > 25:  # skip tiny fragments
            texts.append(t)

    body = "\n\n".join(texts)
    # Hard limit to keep LLM context reasonable
    if len(body) > 3500:
        body = body[:3500].rsplit(" ", 1)[0] + "\n\n[… content truncated …]"

    if not body:
        return f"Fetched '{url}' but could not extract readable text."

    header = f"Page: {title or '(no title)'}\nURL: {url}\n\n"
    return header + body


# ---------------------------------------------------------------------------
# Wikipedia (REST summary – fast & reliable)
# ---------------------------------------------------------------------------

def wikipedia(query: str) -> str:
    """
    Search Wikipedia and return a short summary of the top matching page.
    Example: wikipedia: CRISPR gene editing
    """
    query = query.strip()
    if not query:
        return "Error: empty query"

    headers = {**_DEFAULT_HEADERS, "User-Agent": "ResearchAssistantAgent/1.0 (educational)"}

    try:
        with _get_client() as client:
            # Try exact title first
            title_slug = query.replace(" ", "_")
            r = client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title_slug)}",
                headers=headers,
            )
            if r.status_code == 200:
                page = r.json()
                if page.get("type") != "disambiguation":
                    return _format_wiki_page(page)

            # OpenSearch fallback
            r = client.get(
                "https://en.wikipedia.org/w/api.php",
                params={
                    "action": "opensearch",
                    "search": query,
                    "limit": 1,
                    "namespace": 0,
                    "format": "json",
                },
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            titles = data[1] if len(data) > 1 else []
            if not titles:
                return f"No Wikipedia results found for '{query}'."

            title = titles[0]
            r2 = client.get(
                f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(title)}",
                headers=headers,
            )
            r2.raise_for_status()
            return _format_wiki_page(r2.json())
    except Exception as e:
        return f"Error querying Wikipedia: {e}"


def _format_wiki_page(page: dict) -> str:
    extract = (page.get("extract") or "").strip()
    description = (page.get("description") or "").strip()
    display_title = page.get("title") or "Unknown"
    page_url = page.get("content_urls", {}).get("desktop", {}).get("page", "")

    if not extract and not description:
        return f"Found page '{display_title}' but no summary available."

    summary = extract or description
    if len(summary) > 900:
        summary = summary[:900].rsplit(" ", 1)[0] + "…"

    header = f"Wikipedia – {display_title}"
    if description and description.lower() not in summary.lower():
        header += f" ({description})"
    if page_url:
        header += f"\nURL: {page_url}"
    return f"{header}\n\n{summary}"


# ---------------------------------------------------------------------------
# Current UTC time (useful for dated research)
# ---------------------------------------------------------------------------

def current_time(_: str = "") -> str:
    """
    Return the current date and time in UTC.
    Example: current_time:
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC (%A)")


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, tuple[Callable[..., str], str]] = {
    "web_search": (
        web_search,
        "Search the public web and return titles, URLs and short snippets. "
        "Use this first to discover relevant sources. "
        "Example: web_search: impact of large language models on education 2024",
    ),
    "browse_url": (
        browse_url,
        "Fetch a specific URL and extract the main readable text (title + body). "
        "Use after web_search when you need the full content of a promising page. "
        "Example: browse_url: https://example.com/article",
    ),
    "wikipedia": (
        wikipedia,
        "Look up a topic on Wikipedia and return a concise summary + page URL. "
        "Good for background definitions and established facts. "
        "Example: wikipedia: transformer architecture deep learning",
    ),
    "current_time": (
        current_time,
        "Get the current UTC date and time. Useful when the research needs a timestamp. "
        "Example: current_time:",
    ),
}


def run_tool(name: str, argument: str) -> str:
    """Execute a tool by name and return its string result."""
    if name not in TOOLS:
        return f"Error: unknown tool '{name}'. Available tools: {', '.join(TOOLS)}"
    func, _ = TOOLS[name]
    try:
        # web_search accepts an optional second arg via "query | 8"
        if name == "web_search" and "|" in argument:
            q, n = argument.split("|", 1)
            try:
                return func(q.strip(), max_results=int(n.strip()))
            except ValueError:
                return func(argument)
        return func(argument)
    except Exception as e:
        return f"Error running tool '{name}': {e}"


def tool_descriptions() -> str:
    """Format tool descriptions for the system prompt."""
    lines = []
    for name, (_, desc) in TOOLS.items():
        lines.append(f"- {name}: {desc}")
    return "\n".join(lines)
