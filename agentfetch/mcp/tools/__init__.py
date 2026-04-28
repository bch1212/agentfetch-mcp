"""MCP tool implementations.

Each tool is a thin wrapper over `agentfetch.core.pipeline`. Keep them thin —
all real logic lives in the pipeline so the REST API and MCP server stay in
sync.
"""
