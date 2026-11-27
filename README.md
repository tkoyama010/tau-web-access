# tau-web-access

Web search and content extraction extension for [Tau](https://github.com/huggingface/tau) coding agent.

Provides tools to search the web and fetch web content, enabling the agent to access up-to-date information from the internet.

## Features

- **`web_search`** — Search the web using DuckDuckGo Instant Answer API (no API key required)
- **`web_fetch`** — Fetch and extract readable text content from any web page URL
- Automatic HTML-to-text conversion with script/style removal
- Configurable result limits and content truncation

## Installation

```bash
tau install git:github.com/tkoyama010/tau-web-access
```

Or manually copy `extension.py` to `~/.tau/extensions/`:

```bash
mkdir -p ~/.tau/extensions
cp extension.py ~/.tau/extensions/tau_web_access.py
```

## Usage

Once installed, the agent can use these tools automatically:

### web_search

Search the web for information.

**Parameters:**
- `query` (required): The search query string
- `max_results` (optional, default: 5): Maximum number of results (1-10)

### web_fetch

Fetch and read content from a web page.

**Parameters:**
- `url` (required): The URL to fetch
- `max_length` (optional, default: 4000): Maximum characters to return (500-20000)

## Examples

Ask the agent:

```
Search the web for the latest Python 3.13 release notes
```

```
Fetch the content from https://docs.python.org/3/whatsnew/3.13.html
```

## Requirements

- Tau coding agent (v0.4.0+)
- Python 3.12+
- `httpx` (included with Tau; falls back to `urllib` if unavailable)

## How It Works

- **Search**: Uses the free DuckDuckGo Instant Answer API, which requires no API key. Results are limited compared to paid search APIs.
- **Fetch**: Makes HTTP GET requests with a browser-like User-Agent, follows redirects, and extracts readable text from HTML.

## Limitations

- DuckDuckGo Instant Answer API provides limited results compared to full web search
- Some websites may block automated requests
- JavaScript-rendered content is not supported (static HTML only)

For more comprehensive web access, consider integrating with paid APIs (Brave Search, Tavily, etc.).

## License

MIT License — see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please open an issue or pull request on GitHub.
