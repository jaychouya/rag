#!/usr/bin/env python3
"""
Simple MCP client example with OAuth authentication support.

This client connects to an MCP server using streamable HTTP transport with OAuth.

"""
import asyncio
import json
import os
from datetime import timedelta
from typing import Any

from mcp import ProgressNotification
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import Implementation


class NoAuthClient:
    """MCP client without authentication."""

    def __init__(self, server_url: str, transport_type: str = "streamable_http"):
        self.server_url = server_url
        self.transport_type = transport_type
        self.session: ClientSession | None = None

    async def connect(self):
        """Connect to the MCP server without authentication."""
        print(f"🔗 Attempting to connect to {self.server_url}...")
        try:
            if self.transport_type == "sse":
                print("📡 Opening SSE transport connection...")
                async with sse_client(
                    url=self.server_url,
                    timeout=60,
                ) as (read_stream, write_stream):
                    await self._run_session(read_stream, write_stream, None)
            else:
                print("📡 Opening StreamableHTTP transport connection...")
                async with streamablehttp_client(
                    url=self.server_url,
                    timeout=timedelta(seconds=60),
                ) as (read_stream, write_stream, get_session_id):
                    await self._run_session(read_stream, write_stream, get_session_id)

        except Exception as e:
            print(f"❌ Failed to connect: {e}")
            import traceback

            traceback.print_exc()
    
    async def message_handler(self, message: Any):
        if isinstance(message.root, ProgressNotification):
            print(message.root.params.message)

    async def _run_session(self, read_stream, write_stream, get_session_id):
        """Run the MCP session with the given streams."""
        print("🤝 Initializing MCP session...")
        client_info_data = {
            "name": "testagent", 
            "version": "1.0.0", 
            "_meta": {"law-category-scopes": ["a", "b"]}
        }
        clientInfo = Implementation(**client_info_data)
        async with ClientSession(read_stream, write_stream, client_info=clientInfo, read_timeout_seconds=timedelta(seconds=10)) as session:
            print("⚡ Starting session initialization...")
            self.session = session
            await session.initialize()
            print("✨ Session initialization complete!")
            print(f"\n✅ Connected to MCP server at {self.server_url}")
            if get_session_id:
                session_id = get_session_id()
                if session_id:
                    print(f"Session ID: {session_id}")

            # Run interactive loop

            # pmt = await self.get_prompts()
            # print(f"📜 Prompt template: {pmt.messages[0].content.text}")
            
            # 示例1: 专业场景调用
            professional_metadata = {
                "metadata": {
                "business_scenario": "professional",
                "user_level": "expert",
                "department": "legal",
                "priority": "high"}
            }
            
            await self.call_tool("query_law_by_case_info", 
                               {"userquery": "张某父母育有三名子女，2013年父亲去世，未立遗嘱，2015年母亲去世前，在两位好友的见证下，以录像方式立下遗嘱，表示在自己生病期间张某一直尽心照料，决定把一套房产留给张某，存款12万元则留给张某的两个姐姐。张某的两个姐姐认为录像形式的遗嘱并非有效遗嘱，父母遗产应该按法定继承方式分割。"},
                               metadata=professional_metadata)
            
            # 示例2: 简单场景调用
            simple_metadata = {
                "metadata": {
                "business_scenario": "simple",
                "user_level": "beginner",
                "department": "hr",
                "priority": "normal"}
            }
            await self.call_tool("query_law_by_case_info", 
                               {"userquery": "员工加班费如何计算？"},
                               metadata=simple_metadata)
            #await self.call_tool("hello_unicode", {"count": 3})

    async def list_tools(self):
        """List available tools from the server."""
        if not self.session:
            print("❌ Not connected to server")
            return

        try:
            result = await self.session.list_tools()
            if hasattr(result, "tools") and result.tools:
                print("\n📋 Available tools:")
                for i, tool in enumerate(result.tools, 1):
                    print(f"{i}. {tool.name}")
                    if tool.description:
                        print(f"   Description: {tool.description}")
                    print()
            else:
                print("No tools available")
        except Exception as e:
            print(f"❌ Failed to list tools: {e}")
      
    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None, metadata: dict[str, Any] | None = None):
        async def my_progress_handler(progress: float, total: float | None, message: str | None) -> None:
            if total is not None:
                percentage = (progress / total) * 100
                print(f"Progress: {percentage:.1f}% - {message or ''}")
            else:
                print(f"Progress: {progress} - {message or ''}")

        """Call a specific tool."""
        if not self.session:
            print("❌ Not connected to server")
            return
        try:
            # 准备元数据
            meta_data = {
                "progressToken": "abc123",
                "metadata": metadata or {}
            }
            
            # 确保arguments不为None
            if arguments is None:
                arguments = {}
            
            arguments["meta"] = meta_data
            result = await self.session.call_tool(tool_name, arguments,progress_callback=my_progress_handler)
            print(f"\n🔧 Tool '{tool_name}' result:")

            if hasattr(result, "structuredContent"):
                # structuredContent JSON 字符串输出
                try:
                    formatted_json = json.dumps(result.structuredContent, indent=2, ensure_ascii=False)
                    print(formatted_json)
                except Exception as e:
                    print("❌ Failed to format structuredContent as JSON:", e)
                    print(result.structuredContent)
            elif hasattr(result, "content"):
                for content in result.content:
                    if content.type == "text":
                        print(content.text)
                    else:
                        print(content)
            else:
                print(result)

        except Exception as e:
            print(f"❌ Failed to call tool '{tool_name}': {e}")


async def main():
    """Main entry point."""
    # Default server URL - can be overridden with environment variable
    # Most MCP streamable HTTP servers use /mcp as the endpoint
    # server_url = os.getenv("MCP_SERVER_PORT", 8000)
    transport_type = os.getenv("MCP_TRANSPORT_TYPE", "streamable_http")
    server_url = f"http://192.168.3.159:3000/mcp" if transport_type == "streamable_http" else f"http://192.168.3.159:3000/mcp"

    print("🚀 Simple MCP Auth Client")
    print(f"Connecting to: {server_url}")
    print(f"Transport type: {transport_type}")

    # Start connection flow - OAuth will be handled automatically
    client = NoAuthClient(server_url, transport_type)
    await client.connect()


def cli():
    """CLI entry point for uv script."""
    asyncio.run(main())


if __name__ == "__main__":
    cli()
