"""
MCP Server for AI Test Generation Tool.

Implements the Model Context Protocol for integration with AI assistants.
"""
import asyncio
import json
import sys
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.tools import TestGenTools, MCP_TOOL_DEFINITIONS, ToolResult


class MCPServer:
    """
    MCP Server implementation for AI Test Generation.

    Provides tools for:
    - Project management (list, create, discover)
    - Test case generation
    - Test case upload to ADO
    - Story analysis
    """

    def __init__(self):
        self.tools = TestGenTools()
        self.server_info = {
            "name": "ai-test-gen",
            "version": "2.0.0",
            "description": "AI-powered test case generation tool with multi-project support"
        }

    def get_server_info(self) -> Dict:
        """Get server information."""
        return self.server_info

    def list_tools(self) -> list:
        """List available tools."""
        return MCP_TOOL_DEFINITIONS

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict:
        """
        Call a tool by name with given arguments.

        Args:
            name: Tool name.
            arguments: Tool arguments.

        Returns:
            Tool result as dictionary.
        """
        # Map tool names to methods
        tool_methods = {
            'list_projects': self.tools.list_projects,
            'get_project_config': self.tools.get_project_config,
            'create_project': self.tools.create_project,
            'discover_project': self.tools.discover_project,
            'generate_test_cases': self.tools.generate_test_cases,
            'upload_test_cases': self.tools.upload_test_cases,
            'analyze_story': self.tools.analyze_story,
        }

        method = tool_methods.get(name)
        if not method:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}]
            }

        try:
            result = method(**arguments)

            if result.success:
                return {
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "success": True,
                            "message": result.message,
                            "data": result.data
                        }, indent=2)
                    }]
                }
            else:
                return {
                    "isError": True,
                    "content": [{
                        "type": "text",
                        "text": json.dumps({
                            "success": False,
                            "message": result.message,
                            "error": result.error
                        }, indent=2)
                    }]
                }
        except Exception as e:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool execution failed: {str(e)}"}]
            }

    async def handle_message(self, message: Dict) -> Dict:
        """
        Handle incoming MCP message.

        Args:
            message: MCP protocol message.

        Returns:
            Response message.
        """
        method = message.get('method', '')
        params = message.get('params', {})
        msg_id = message.get('id')

        if method == 'initialize':
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": self.server_info
                }
            }

        elif method == 'tools/list':
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "tools": self.list_tools()
                }
            }

        elif method == 'tools/call':
            tool_name = params.get('name', '')
            arguments = params.get('arguments', {})
            result = await self.call_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": result
            }

        elif method == 'notifications/initialized':
            # Client acknowledged initialization
            return None

        else:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def run_stdio(self):
        """Run server using stdio transport."""
        print("AI Test Gen MCP Server starting...", file=sys.stderr)

        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)

        loop = asyncio.get_event_loop()
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

        while True:
            try:
                # Read Content-Length header
                line = await reader.readline()
                if not line:
                    break

                line = line.decode('utf-8').strip()
                if not line.startswith('Content-Length:'):
                    continue

                content_length = int(line.split(':')[1].strip())

                # Skip empty line
                await reader.readline()

                # Read content
                content = await reader.read(content_length)
                message = json.loads(content.decode('utf-8'))

                # Handle message
                response = await self.handle_message(message)

                if response:
                    response_bytes = json.dumps(response).encode('utf-8')
                    header = f"Content-Length: {len(response_bytes)}\r\n\r\n"
                    writer.write(header.encode('utf-8'))
                    writer.write(response_bytes)
                    await writer.drain()

            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                break


def create_server() -> MCPServer:
    """Create a new MCP server instance."""
    return MCPServer()


async def main():
    """Main entry point for MCP server."""
    server = create_server()
    await server.run_stdio()


if __name__ == '__main__':
    asyncio.run(main())
