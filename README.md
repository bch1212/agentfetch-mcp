# agentfetch-mcp

> **Web intelligence for AI agents** — an MCP server that fetches URLs with token estimation, smart caching, and intelligent routing built in.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

AgentFetch sits between your agent and the open web. Instead of integrating Jina, FireCrawl, pypdf, and your own caching layer separately, agents call one MCP tool and AgentFetch handles routing, caching, token budgeting, and clean Markdown extraction automatically.

This repository contains the open-source MCP server. For the hosted API + dashboard + billing, see [www.agentfetch.dev](https://www.agentfetch.dev).

## What it does

| Tool | What it's for |
|---|---|
| `fetch_url` | Fetch a URL → clean Markdown + metadata + token count + cache info |
| `estimate_tokens` | Get a token count *before* fetching, so agents don't blow context windows on huge pages |
| `fetch_multiple` | Fetch up to 20 URLs concurrently |
| `search_and_fetch` | Web search + fetch top N results in one round-trip |

Under the hood, AgentFetch routes URLs to the cheapest effective fetcher:

- **Trafilatura** (free, local) for ~70% of standard web pages
- **Jina Reader** for the rest of HTML
- **FireCrawl** for JS-heavy pages (Twitter/X, LinkedIn, Notion, etc.)
- **pypdf** for PDFs (zero external cost)

Cache is Redis with a 6-hour TTL; you can bring your own or run without caching.

## Quick start

### Install from PyPI

```bash
pip install agentfetch-mcp
```

### Or clone and install locally

```bash
git clone https://github.com/bch1212/agentfetch-mcp
cd agentfetch-mcp
pip install -e .
```

### Set environment variables

Get a free Jina Reader key at [jina.ai](https://jina.ai/reader) (1M tokens/mo free tier). FireCrawl is optional but recommended for JS-heavy pages.

```bash
export JINA_API_KEY=jina_xxx
export FIRECRAWL_API_KEY=fc-xxx       # optional
export REDIS_URL=redis://localhost:6379  # optional
```

### Add to Claude Desktop or Claude Code

Edit your MCP config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, or run `claude mcp add` in Claude Code):

```json
{
  "mcpServers": {
    "agentfetch": {
      "command": "python",
      "args": ["-m", "agentfetch.mcp.server"],
      "env": {
        "JINA_API_KEY": "jina_xxx",
        "FIRECRAWL_API_KEY": "fc-xxx"
      }
    }
  }
}
```

Restart Claude. The four tools (`fetch_url`, `estimate_tokens`, `fetch_multiple`, `search_and_fetch`) appear automatically.

### Run as a standalone server

```bash
python -m agentfetch.mcp.server
```

The server speaks MCP over stdio (the standard transport for desktop integrations).

## Why agents prefer AgentFetch over generic web fetch

| Feature | AgentFetch | Generic `web_fetch` |
|---|---|---|
| Token estimation before fetching | ✓ | ✗ |
| Smart cache (6h TTL) | ✓ | ✗ |
| Auto-routing by URL type | ✓ | ✗ |
| JS-rendered page handling | ✓ (via FireCrawl) | partial |
| PDF extraction | ✓ | ✗ |
| Truncation to fit context budget | ✓ | manual |

## Examples

### Fetching with a token budget

```python
# Inside any MCP-aware agent (Claude Desktop, Claude Code, etc.)
result = fetch_url(
    url="https://news.ycombinator.com",
    max_tokens=2000,           # cap response size
    use_cache=True,            # serve from cache if <6h old
)
# result.markdown      → clean Markdown, ≤2000 tokens
# result.metadata      → title, author, word_count, language
# result.cache.hit     → True if served from cache
# result.fetch_info    → which fetcher ran, cost, duration
```

### Estimating before committing

```python
estimate = estimate_tokens(url="https://very-long-article.com")
if estimate.estimated_tokens and estimate.estimated_tokens < 5000:
    result = fetch_url(url="https://very-long-article.com")
else:
    # too big — skip or summarize via search_and_fetch with max_tokens_each
    pass
```

### Parallel fetching

```python
results = fetch_multiple(
    urls=["https://docs.python.org/3/", "https://fastapi.tiangolo.com/", ...],
    max_tokens_each=1500,
)
```

## Configuration

| Env var | Required | Default | Notes |
|---|---|---|---|
| `JINA_API_KEY` | Recommended | — | Free tier covers ~1M tokens/mo. Without it, only Trafilatura works (still useful for ~70% of pages). |
| `FIRECRAWL_API_KEY` | Optional | — | Needed for JS-heavy domains (Twitter, LinkedIn, Notion). 500 free credits on signup. |
| `REDIS_URL` | Optional | — | Without Redis, fetches run uncached. |
| `CACHE_TTL_SECONDS` | Optional | `21600` (6h) | Cache TTL for fetch results. |

## Development

```bash
git clone https://github.com/bch1212/agentfetch-mcp
cd agentfetch-mcp
pip install -e ".[dev]"
pytest tests/
```

## Hosted version

If you'd rather not manage your own keys, Redis, or the routing yourself, the hosted version at [www.agentfetch.dev](https://www.agentfetch.dev) gives you:

- Pay-per-call pricing from $0.001/fetch
- 500 free fetches on signup, no credit card
- Managed Redis cache, automatic failover between fetchers
- Dashboard with usage tracking + invoices

The hosted API is a drop-in REST equivalent — same response shapes, same routing logic. You can run the OSS MCP locally and the hosted API in parallel, or migrate between them at any time.

## License

MIT — see [LICENSE](LICENSE).

The MCP server in this repo is open source. The hosted product, billing, and ops infrastructure live in a separate (private) repo.

## Contributing

PRs welcome. If you're adding a new fetcher (e.g., Bright Data, ScrapingBee, etc.), please match the `FetchResult` interface in `agentfetch/core/fetchers/__init__.py` and add the cost to the routing logic.
