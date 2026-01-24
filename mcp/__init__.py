"""
MCP (Model Context Protocol) Server for AI Test Generation Tool.

This module provides MCP integration allowing AI assistants to:
1. Generate test cases for any project
2. Discover and configure new applications
3. Upload test cases to Azure DevOps
4. Manage project configurations

Usage:
    # Start MCP server
    python -m mcp.server

    # Or use with Claude Desktop/other MCP clients
"""
from .server import MCPServer, create_server
from .tools import TestGenTools

__all__ = ['MCPServer', 'create_server', 'TestGenTools']
