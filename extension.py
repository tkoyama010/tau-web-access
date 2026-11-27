"""Web search and content extraction extension for Tau coding agent.

Provides tools to search the web and fetch web content, enabling the agent
to access up-to-date information from the internet.

Installation:
    tau install git:github.com/YOUR_USERNAME/tau-web-access

Or copy to ~/.tau/extensions/
"""

from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus, urljoin

from tau_agent.messages import TextContent
from tau_agent.tools import (
    AgentTool,
    AgentToolResult,
    ToolCancellationToken,
    ToolUpdateCallback,
)
from tau_agent.types import JSONValue
from tau_coding.extensions import ExtensionAPI

# Try to import httpx, fallback to urllib if not available
try:
    import httpx
    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False
    import urllib.request
    import urllib.error


class HTMLTextExtractor(HTMLParser):
    """Simple HTML to text converter."""

    def __init__(self):
        super().__init__()
        self.result = []
        self.skip = False
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link', 'nav'}

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.skip = True
        if tag in {'p', 'br', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'}:
            self.result.append('\n')

    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self.skip = False

    def handle_data(self, data):
        if not self.skip:
            self.result.append(data)

    def get_text(self):
        text = ''.join(self.result)
        # Clean up whitespace
        lines = [line.strip() for line in text.split('\n')]
        return '\n'.join(line for line in lines if line)


def extract_text_from_html(html: str) -> str:
    """Extract readable text from HTML content."""
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html)
        return extractor.get_text()
    except Exception:
        # Fallback: remove tags with regex
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        return ' '.join(text.split())


async def fetch_url(url: str, timeout: float = 10.0) -> tuple[str, str]:
    """Fetch URL content and return (content_type, body).

    Returns:
        Tuple of (content_type, body_text)
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; TauWebAccess/1.0)'
    }

    if HAS_HTTPX:
        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
            response = await client.get(url, headers=headers)
            content_type = response.headers.get('content-type', '')
            return content_type, response.text
    else:
        # Fallback to urllib (synchronous)
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=int(timeout)) as response:
                content_type = response.headers.get('content-type', '')
                body = response.read().decode('utf-8', errors='ignore')
                return content_type, body
        except urllib.error.HTTPError as e:
            raise Exception(f"HTTP Error {e.code}: {e.reason}")


async def search_duckduckgo(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search using DuckDuckGo Instant Answer API.

    Note: This uses the free instant answer API which provides limited results.
    For comprehensive search, consider using a paid search API.

    Args:
        query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of dicts with 'title', 'url', 'snippet' keys
    """
    results = []

    # DuckDuckGo Instant Answer API
    api_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_html=1"

    try:
        _, body = await fetch_url(api_url, timeout=5.0)
        import json
        data = json.loads(body)

        # Abstract (main answer)
        if data.get('Abstract'):
            results.append({
                'title': data.get('Heading', 'Answer'),
                'url': data.get('AbstractURL', ''),
                'snippet': data['Abstract']
            })

        # Related topics
        for topic in data.get('RelatedTopics', [])[:max_results - len(results)]:
            if isinstance(topic, dict) and 'Text' in topic:
                results.append({
                    'title': topic.get('Text', '')[:60],
                    'url': topic.get('FirstURL', ''),
                    'snippet': topic.get('Text', '')
                })

    except Exception as e:
        # If API fails, return empty results with error info
        results.append({
            'title': 'Search Error',
            'url': '',
            'snippet': f'Could not fetch search results: {str(e)}'
        })

    return results[:max_results]


async def _run_web_search(
    tool_call_id: str,
    arguments: Mapping[str, JSONValue],
    signal: ToolCancellationToken | None = None,
    on_update: ToolUpdateCallback | None = None,
) -> AgentToolResult:
    """Execute web search tool."""
    del tool_call_id, signal, on_update

    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        return AgentToolResult(
            content=[TextContent(text="Error: 'query' must be a non-empty string.")]
        )

    max_results = int(arguments.get("max_results", 5))
    max_results = min(max(1, max_results), 10)

    try:
        results = await search_duckduckgo(query.strip(), max_results)

        if not results:
            return AgentToolResult(
                content=[TextContent(text=f"No results found for: {query}")]
            )

        output_lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            output_lines.append(f"{i}. {r['title']}")
            if r['url']:
                output_lines.append(f"   URL: {r['url']}")
            if r['snippet']:
                output_lines.append(f"   {r['snippet'][:200]}")
            output_lines.append("")

        return AgentToolResult(
            content=[TextContent(text='\n'.join(output_lines))],
            details={"results": results}
        )

    except Exception as e:
        return AgentToolResult(
            content=[TextContent(text=f"Search error: {str(e)}")]
        )


async def _run_web_fetch(
    tool_call_id: str,
    arguments: Mapping[str, JSONValue],
    signal: ToolCancellationToken | None = None,
    on_update: ToolUpdateCallback | None = None,
) -> AgentToolResult:
    """Execute web fetch tool."""
    del tool_call_id, signal, on_update

    url = arguments.get("url")
    if not isinstance(url, str) or not url.strip():
        return AgentToolResult(
            content=[TextContent(text="Error: 'url' must be a non-empty string.")]
        )

    url = url.strip()

    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    max_length = int(arguments.get("max_length", 4000))
    max_length = min(max(500, max_length), 20000)

    try:
        content_type, body = await fetch_url(url)

        # Check if it's HTML
        if 'html' in content_type.lower():
            text = extract_text_from_html(body)
        else:
            text = body

        # Truncate if needed
        if len(text) > max_length:
            text = text[:max_length] + f"\n\n[Content truncated at {max_length} characters]"

        output = f"Content from: {url}\n{'='*60}\n\n{text}"

        return AgentToolResult(
            content=[TextContent(text=output)],
            details={"url": url, "content_type": content_type, "length": len(text)}
        )

    except Exception as e:
        return AgentToolResult(
            content=[TextContent(text=f"Fetch error for {url}: {str(e)}")]
        )


def setup(tau: ExtensionAPI) -> None:
    """Register web access tools for Tau."""

    # Web Search Tool
    tau.register_tool(
        AgentTool(
            name="web_search",
            label="web search",
            description=(
                "Search the web for information. Returns a list of results with titles, "
                "URLs, and snippets. Use this to find up-to-date information, documentation, "
                "or answers to questions that require internet access."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 1,
                        "description": "The search query to look up.",
                    },
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 10,
                        "default": 5,
                        "description": "Maximum number of results to return (default: 5).",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            execute_fn=_run_web_search,
            prompt_snippet="Search the web for up-to-date information.",
            prompt_guidelines=(
                "Use web_search when you need current information, documentation, "
                "or facts that may not be in your training data.",
            ),
        )
    )

    # Web Fetch Tool
    tau.register_tool(
        AgentTool(
            name="web_fetch",
            label="web fetch",
            description=(
                "Fetch and extract readable content from a web page URL. "
                "Converts HTML to plain text for easy reading. "
                "Use this to read full articles, documentation, or any web page content."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "minLength": 1,
                        "description": "The URL of the web page to fetch.",
                    },
                    "max_length": {
                        "type": "integer",
                        "minimum": 500,
                        "maximum": 20000,
                        "default": 4000,
                        "description": "Maximum characters to return (default: 4000).",
                    },
                },
                "required": ["url"],
                "additionalProperties": False,
            },
            execute_fn=_run_web_fetch,
            prompt_snippet="Fetch and read content from a web page.",
            prompt_guidelines=(
                "Use web_fetch to read full content from URLs found in search results "
                "or provided by the user. Content is automatically cleaned and truncated "
                "to a readable length.",
            ),
        )
    )

    # Add a prompt guideline about web access
    tau.add_prompt_guideline(
        "When you need current information or facts beyond your knowledge cutoff, "
        "use web_search to find relevant pages and web_fetch to read their content."
    )
