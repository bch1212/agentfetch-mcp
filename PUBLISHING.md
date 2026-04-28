# Publishing to the official MCP Registry

The MCP Registry (https://registry.modelcontextprotocol.io/) is Anthropic's
official directory for MCP servers. Listing here makes AgentFetch
discoverable from inside Claude Desktop and Claude Code's "Add MCP server"
flow — highest-leverage distribution channel.

The Registry only stores metadata; it points at a real package on a
real package registry (PyPI for Python). So step 1 is publishing to PyPI.

## Prerequisites (one-time)

1. **PyPI account** — create at https://pypi.org/account/register/. Use 2FA.
2. **PyPI API token** — at https://pypi.org/manage/account/token/, create a
   token scoped to the project `agentfetch-mcp` (you'll need to publish once
   first, then narrow scope). Save the token.
3. **mcp-publisher CLI**:
   ```bash
   brew install mcp-publisher
   ```

## Step 1 — Publish to PyPI

```bash
cd ~/Projects/agentic-builds/agentfetch-mcp   # or wherever you cloned it

# Build the dist
python -m pip install --upgrade build twine
python -m build

# Upload to PyPI
python -m twine upload dist/* -u __token__ -p <your-pypi-token>
```

Verify at https://pypi.org/project/agentfetch-mcp/.

## Step 2 — Publish to the MCP Registry

`server.json` already exists in the repo root. It declares the package as
`pypi:agentfetch-mcp`. The `mcpName` in `pyproject.toml` is matched against
this for ownership verification.

```bash
mcp-publisher login        # opens browser for GitHub OAuth
mcp-publisher publish      # reads server.json, registers metadata
```

After this, the server appears at
https://registry.modelcontextprotocol.io/?search=agentfetch and is
installable via Claude Desktop's MCP picker.

## Updating the listing

When you ship a new version:
1. Bump `version` in `pyproject.toml` AND `server.json`
2. `python -m build && twine upload dist/*`
3. `mcp-publisher publish`

The Registry is preview-tier, so expect occasional breaking changes through
mid-2026.
