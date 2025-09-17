import asyncio
import json
from typing import Dict, Any, List, Optional
from google.adk.agents import Agent
import os
import aiohttp
import ssl
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class MCPSSEClient:
    """MCP (Model Context Protocol) client that communicates with JIRA MCP server via HTTP Server-Sent Events (SSE).
    
    This client handles authentication with Snowflake tokens and manages the complex SSE-based
    communication protocol required for the JIRA MCP server integration.
    """

    def __init__(self, sse_url: str, snowflake_token: str):
        if not sse_url:
            raise ValueError("sse_url cannot be None or empty. Please check your JIRA_MCP_SSE_URL environment variable.")
        if not snowflake_token:
            raise ValueError("snowflake_token cannot be None or empty. Please check your JIRA_MCP_SNOWFLAKE_TOKEN environment variable.")

        self.sse_url = sse_url
        self.snowflake_token = snowflake_token
        self._session = None
        self._initialized = False
        self._request_id = 0
        self._session_id = None
        self._messages_url = None
        # For simple HTTP approach
        self.base_url = sse_url.replace('/sse', '') if sse_url else ''
        self._sse_connection = None
        self._pending_requests = {}

    async def _ensure_connection(self):
        """Ensure HTTP session is initialized and MCP protocol handshake is completed.
        
        This method establishes the aiohttp session, SSE connection, and completes the
        MCP initialization sequence required before making tool calls.
        """
        if self._session is None:
            # Create SSL context that allows self-signed certificates for internal environments
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self._session = aiohttp.ClientSession(connector=connector)

        # First establish SSE session
        if self._session_id is None:
            await self._establish_sse_session()

        if not self._initialized:
            # Send initialize request via HTTP
            init_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "experimental": {},
                        "prompts": {"listChanged": False},
                        "resources": {"subscribe": False, "listChanged": False},
                        "tools": {"listChanged": False}
                    },
                    "clientInfo": {"name": "adk-agent", "version": "0.1.0"}
                }
            }

            try:
                response = await self._send_http_request(init_request)
                if "error" in response:
                    print(f"WARNING: Initialize failed: {response['error']}, proceeding anyway...")
                else:
                    print(f"DEBUG: Initialize successful: {response}")

                # Send initialized notification
                init_notification = {
                    "jsonrpc": "2.0",
                    "method": "initialized",
                    "params": {}
                }
                await self._send_http_notification(init_notification)

            except Exception as e:
                print(f"WARNING: Initialize process failed: {e}, proceeding anyway...")

            self._initialized = True

    async def _establish_sse_session(self):
        """Establish Server-Sent Events session and extract session ID.
        
        Connects to the SSE endpoint and waits for the session ID to be provided
        in the event stream, which is required for subsequent HTTP requests.
        """
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Snowflake-Token": self.snowflake_token
        }

        print("DEBUG: Establishing SSE session...")

        try:
            async with self._session.get(self.sse_url, headers=headers) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"SSE connection error {resp.status}: {error_text}")

                # Read the first few lines to get session info
                async for line in resp.content:
                    line_str = line.decode('utf-8').strip()
                    print(f"DEBUG: SSE line: {line_str}")

                    if line_str.startswith('event: endpoint'):
                        continue
                    elif line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if '/messages/?session_id=' in data_str:
                            # Extract session ID and construct messages URL
                            session_id = data_str.split('session_id=')[1]
                            self._session_id = session_id
                            # Construct full messages URL
                            base_url = self.sse_url.replace('/sse', '')
                            self._messages_url = f"{base_url}{data_str}"
                            print(f"DEBUG: Got session ID: {session_id}")
                            print(f"DEBUG: Messages URL: {self._messages_url}")
                            break

                if not self._session_id:
                    raise Exception("Failed to get session ID from SSE stream")

        except Exception as e:
            print(f"DEBUG: SSE session establishment failed: {e}")
            raise

    def _get_next_id(self) -> int:
        """Generate next sequential request ID for JSON-RPC protocol.
        
        Returns:
            int: Incremented request ID for tracking request/response pairs
        """
        self._request_id += 1
        return self._request_id

    async def _send_http_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request via messages endpoint and wait for response.
        
        Args:
            request: JSON-RPC request dictionary with id, method, and params
            
        Returns:
            dict: Response from the MCP server
            
        Raises:
            Exception: If session not established or HTTP request fails
        """
        if not self._session or not self._messages_url:
            raise Exception("Session not properly established")

        headers = {
            "Content-Type": "application/json",
            "X-Snowflake-Token": self.snowflake_token
        }

        print(f"DEBUG: Sending request to {self._messages_url}: {request}")

        try:
            # POST the JSON request to the messages endpoint
            async with self._session.post(
                self._messages_url,
                json=request,
                headers=headers
            ) as resp:
                if resp.status == 202:
                    print("DEBUG: Request accepted (202) - waiting for async response via SSE")
                    # Wait for the response via SSE
                    return await self._wait_for_sse_response(request["id"])
                elif resp.status == 200:
                    response = await resp.json()
                    print(f"DEBUG: Received immediate response: {response}")
                    return response
                else:
                    error_text = await resp.text()
                    raise Exception(f"Messages endpoint error {resp.status}: {error_text}")

        except Exception as e:
            print(f"DEBUG: Messages request failed: {e}")
            raise

    async def _wait_for_sse_response(self, request_id: int) -> Dict[str, Any]:
        """Wait for response from SSE stream matching the given request ID.
        
        Args:
            request_id: The JSON-RPC request ID to match against responses
            
        Returns:
            dict: The matching response from the SSE stream
            
        Raises:
            Exception: If timeout occurs or no matching response found
        """
        headers = {
            "Accept": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Snowflake-Token": self.snowflake_token
        }

        # Listen to the original SSE endpoint for the response
        sse_listen_url = f"{self.sse_url}?session_id={self._session_id}"
        print(f"DEBUG: Listening for SSE response at: {sse_listen_url}")

        try:
            # Add timeout to prevent hanging
            timeout = aiohttp.ClientTimeout(total=30)
            async with self._session.get(sse_listen_url, headers=headers, timeout=timeout) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise Exception(f"SSE listen error {resp.status}: {error_text}")

                line_count = 0
                async for line in resp.content:
                    line_str = line.decode('utf-8').strip()
                    if line_str:  # Only print non-empty lines
                        print(f"DEBUG: SSE response line: {line_str}")

                    line_count += 1
                    if line_count > 1000:  # Prevent infinite loops
                        break

                    if line_str.startswith('data: '):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str and data_str != '[DONE]' and not data_str.startswith('/messages/'):
                            try:
                                response = json.loads(data_str)
                                # Check if this is the response for our request
                                if response.get("id") == request_id:
                                    print(f"DEBUG: Found matching response: {response}")
                                    return response
                                else:
                                    print(f"DEBUG: Response ID {response.get('id')} doesn't match request ID {request_id}")
                            except json.JSONDecodeError as e:
                                print(f"DEBUG: Failed to parse JSON: {data_str}, error: {e}")
                                continue

                raise Exception(f"No response received for request ID {request_id} in {line_count} lines")

        except asyncio.TimeoutError:
            raise Exception(f"Timeout waiting for response to request ID {request_id}")
        except Exception as e:
            print(f"DEBUG: SSE response wait failed: {e}")
            raise

    async def _send_http_notification(self, notification: Dict[str, Any]):
        """Send a JSON-RPC notification via messages endpoint (no response expected).
        
        Args:
            notification: JSON-RPC notification dictionary with method and params
        """
        if not self._session or not self._messages_url:
            print("WARNING: Session not properly established for notification")
            return

        headers = {
            "Content-Type": "application/json",
            "X-Snowflake-Token": self.snowflake_token
        }

        try:
            async with self._session.post(self._messages_url, json=notification, headers=headers) as resp:
                if resp.status not in [200, 202]:
                    error_text = await resp.text()
                    print(f"WARNING: Notification returned status {resp.status}: {error_text}")
        except Exception as e:
            print(f"WARNING: Failed to send notification: {e}")

    async def call_tool_simple_http(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool using direct HTTP POST without SSE complexity.
        
        This is a simplified approach that bypasses the SSE protocol for direct tool calls.
        
        Args:
            tool_name: Name of the MCP tool to call
            **kwargs: Arguments to pass to the tool
            
        Returns:
            dict: Result from the MCP server or error information
        """
        try:
            if self._session is None:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                self._session = aiohttp.ClientSession(connector=connector)

            # Try direct tool call
            tool_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_id(),
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": {k: v for k, v in kwargs.items() if v is not None}
                }
            }

            headers = {
                "Content-Type": "application/json",
                "X-Snowflake-Token": self.snowflake_token
            }

            # Try the direct tools endpoint
            tools_url = f"{self.base_url}/tools/call"
            print(f"DEBUG: Trying direct call to {tools_url}")

            async with self._session.post(tools_url, json=tool_request, headers=headers) as resp:
                if resp.status == 200:
                    response = await resp.json()
                    print(f"DEBUG: Direct call successful: {response}")
                    return response.get("result", response)
                else:
                    error_text = await resp.text()
                    print(f"DEBUG: Direct call failed {resp.status}: {error_text}")
                    return {"error": f"Direct call failed {resp.status}: {error_text}"}

        except Exception as e:
            return {"error": f"Error in simple HTTP call: {str(e)}"}

    async def call_tool_direct_http(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Try direct HTTP call to a known working endpoint for specific tools.
        
        This method contains hardcoded logic for specific tool calls that have
        been verified to work with direct HTTP requests.
        
        Args:
            tool_name: Name of the MCP tool to call
            **kwargs: Arguments to pass to the tool
            
        Returns:
            dict: Result from the MCP server or error information
        """
        try:
            if self._session is None:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                self._session = aiohttp.ClientSession(connector=connector)

            # For TELCOV10N-682, let's try the working URL pattern from settings
            if tool_name == "get_jira_issue_details" and "issue_keys" in kwargs:
                working_url = "https://jira-mcp-snowflake.apps.int.stc.ai.preprod.us-east-1.aws.paas.redhat.com/tools/call"

                # Use the exact format that was working in curl
                request_payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "tools/call",
                    "params": {
                        "name": "get_jira_issue_details",
                        "arguments": {
                            "issue_keys": kwargs["issue_keys"]
                        }
                    }
                }

                headers = {
                    "Content-Type": "application/json",
                    "X-Snowflake-Token": self.snowflake_token
                }

                print(f"DEBUG: Trying direct call to {working_url}")
                timeout = aiohttp.ClientTimeout(total=30)

                async with self._session.post(working_url, json=request_payload, headers=headers, timeout=timeout) as resp:
                    print(f"DEBUG: Direct call response status: {resp.status}")
                    if resp.status == 200:
                        result = await resp.json()
                        print(f"DEBUG: Direct call result: {result}")
                        return result.get("result", result)
                    else:
                        error_text = await resp.text()
                        print(f"DEBUG: Direct call failed: {error_text}")
                        return {"error": f"Direct call failed {resp.status}: {error_text}"}

            return {"error": "Direct HTTP method not implemented for this tool"}

        except Exception as e:
            print(f"DEBUG: Exception in direct HTTP call: {e}")
            return {"error": f"Error in direct HTTP call: {str(e)}"}

    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool on the JIRA MCP server and wait for the real response.

        Args:
            tool_name: Name of the MCP tool to call
            **kwargs: Arguments to pass to the tool

        Returns:
            dict: Result from the MCP server
        """
        print(f"DEBUG: call_tool starting for {tool_name}")

        # Skip direct HTTP for now, go straight to SSE approach
        print(f"DEBUG: Using SSE approach for {tool_name}")

        try:
            if self._session is None:
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                connector = aiohttp.TCPConnector(ssl=ssl_context)
                self._session = aiohttp.ClientSession(connector=connector)

            headers = {
                "Accept": "text/event-stream",
                "X-Snowflake-Token": self.snowflake_token
            }

            timeout = aiohttp.ClientTimeout(total=15)

            # Start an SSE connection and maintain it for both getting session and listening for response
            print("DEBUG: Starting SSE connection...")
            async with self._session.get(self.sse_url, headers=headers, timeout=timeout) as sse_resp:
                if sse_resp.status != 200:
                    error_text = await sse_resp.text()
                    return {"error": f"SSE connection error {sse_resp.status}: {error_text}"}

                session_id = None
                request_id = None

                # Step 1: Get session ID from the SSE stream
                async for line in sse_resp.content:
                    line_str = line.decode('utf-8').strip()

                    if line_str.startswith('data: /messages/?session_id='):
                        session_id = line_str.split('session_id=')[1]
                        print(f"DEBUG: Got session ID: {session_id}")
                        break

                if not session_id:
                    return {"error": "Failed to get session ID from SSE"}

                # Step 2: Initialize the session first
                messages_url = f"{self.base_url}/messages/?session_id={session_id}"
                post_headers = {
                    "Content-Type": "application/json",
                    "X-Snowflake-Token": self.snowflake_token
                }

                # Initialize the MCP session first
                if not hasattr(self, '_initialized_session'):
                    init_request = {
                        "jsonrpc": "2.0",
                        "id": self._get_next_id(),
                        "method": "initialize",
                        "params": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "experimental": {},
                                "prompts": {"listChanged": False},
                                "resources": {"subscribe": False, "listChanged": False},
                                "tools": {"listChanged": False}
                            },
                            "clientInfo": {"name": "adk-agent", "version": "0.1.0"}
                        }
                    }

                    print("DEBUG: Initializing MCP session...")
                    async with self._session.post(messages_url, json=init_request, headers=post_headers, timeout=timeout) as init_resp:
                        if init_resp.status == 202:
                            # Listen for initialization response
                            async for line in sse_resp.content:
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: ') and not line_str.startswith('data: /messages/'):
                                    data_str = line_str[6:]
                                    if data_str and data_str != '[DONE]':
                                        try:
                                            response = json.loads(data_str)
                                            if response.get("id") == init_request["id"]:
                                                print(f"DEBUG: Initialize response: {response}")

                                                # Send initialized notification
                                                init_notification = {
                                                    "jsonrpc": "2.0",
                                                    "method": "notifications/initialized",
                                                    "params": {}
                                                }

                                                # Send notification (no response expected)
                                                async with self._session.post(messages_url, json=init_notification, headers=post_headers, timeout=timeout) as notif_resp:
                                                    print(f"DEBUG: Initialized notification sent: {notif_resp.status}")

                                                self._initialized_session = True
                                                break
                                        except json.JSONDecodeError:
                                            continue

                # Step 3: List tools to understand the schema
                if not hasattr(self, '_tools_listed'):
                    list_request = {
                        "jsonrpc": "2.0",
                        "id": self._get_next_id(),
                        "method": "tools/list",
                        "params": {}
                    }

                    print("DEBUG: Listing available tools...")
                    async with self._session.post(messages_url, json=list_request, headers=post_headers, timeout=timeout) as list_resp:
                        if list_resp.status == 202:
                            # Listen for tools list response
                            async for line in sse_resp.content:
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: ') and not line_str.startswith('data: /messages/'):
                                    data_str = line_str[6:]
                                    if data_str and data_str != '[DONE]':
                                        try:
                                            response = json.loads(data_str)
                                            if response.get("id") == list_request["id"]:
                                                print(f"DEBUG: Tools list response: {response}")
                                                self._tools_listed = True
                                                break
                                        except json.JSONDecodeError:
                                            continue

                # Try a simpler tool first (get_jira_project_summary takes no args)
                if tool_name == "get_jira_issue_details":
                    # First test with project summary to ensure connection works
                    test_request = {
                        "jsonrpc": "2.0",
                        "id": self._get_next_id(),
                        "method": "tools/call",
                        "params": {
                            "name": "get_jira_project_summary",
                            "arguments": {}
                        }
                    }

                    print("DEBUG: Testing with get_jira_project_summary first...")
                    async with self._session.post(messages_url, json=test_request, headers=post_headers, timeout=timeout) as test_resp:
                        if test_resp.status == 202:
                            # Listen for test response
                            async for line in sse_resp.content:
                                line_str = line.decode('utf-8').strip()
                                if line_str.startswith('data: ') and not line_str.startswith('data: /messages/'):
                                    data_str = line_str[6:]
                                    if data_str and data_str != '[DONE]':
                                        try:
                                            response = json.loads(data_str)
                                            if response.get("id") == test_request["id"]:
                                                print(f"DEBUG: Test response: {response}")
                                                break
                                        except json.JSONDecodeError:
                                            continue

                # Use the correct MCP parameter format
                tool_request = {
                    "jsonrpc": "2.0",
                    "id": self._get_next_id(),
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": {k: v for k, v in kwargs.items() if v is not None}
                    }
                }
                print(f"DEBUG: Using correct MCP format: {tool_request}")

                request_id = tool_request["id"]

                post_headers = {
                    "Content-Type": "application/json",
                    "X-Snowflake-Token": self.snowflake_token
                }

                print(f"DEBUG: Sending tool request {request_id} to {messages_url}")

                # Send the request (without waiting for it to complete)
                async with self._session.post(messages_url, json=tool_request, headers=post_headers, timeout=timeout) as post_resp:
                    print(f"DEBUG: Tool request response status: {post_resp.status}")

                    if post_resp.status not in [200, 202]:
                        error_text = await post_resp.text()
                        return {"error": f"Messages endpoint error {post_resp.status}: {error_text}"}

                # Step 3: Continue listening on the original SSE connection for the response
                print(f"DEBUG: Listening for response to request {request_id}")
                line_count = 0
                max_wait_time = 45  # 45 seconds max
                start_time = asyncio.get_event_loop().time()

                async for line in sse_resp.content:
                    current_time = asyncio.get_event_loop().time()
                    if current_time - start_time > max_wait_time:
                        return {"error": f"Timeout waiting for response to request {request_id}"}

                    line_str = line.decode('utf-8').strip()
                    line_count += 1

                    if line_str and not line_str.startswith(': ping'):
                        print(f"DEBUG: SSE response line {line_count}: {line_str}")

                    if line_count > 2000:  # Prevent infinite loops
                        return {"error": "Too many SSE lines, giving up"}

                    if line_str.startswith('data: ') and not line_str.startswith('data: /messages/'):
                        data_str = line_str[6:]  # Remove 'data: ' prefix
                        if data_str and data_str != '[DONE]':
                            try:
                                response = json.loads(data_str)
                                if response.get("id") == request_id:
                                    print(f"DEBUG: Found matching response for request {request_id}")
                                    if "result" in response:
                                        result = response["result"]
                                        # Extract the actual data from MCP response structure
                                        if isinstance(result, dict) and "structuredContent" in result:
                                            return result["structuredContent"].get("result", result)
                                        else:
                                            return result
                                    elif "error" in response:
                                        return {"error": f"MCP error: {response['error']}"}
                                    else:
                                        return response
                                else:
                                    print(f"DEBUG: Response ID {response.get('id')} doesn't match request ID {request_id}")
                            except json.JSONDecodeError as e:
                                print(f"DEBUG: JSON decode error: {e}")
                                continue

                return {"error": f"No response received for request ID {request_id} after {line_count} lines"}

        except asyncio.TimeoutError:
            return {"error": f"Timeout calling MCP server for {tool_name}"}
        except Exception as e:
            print(f"DEBUG: Exception in call_tool: {e}")
            return {"error": f"Error calling MCP server: {str(e)}"}

    async def close(self):
        """Close the HTTP session and reset connection state.
        
        Properly cleans up the aiohttp session and resets all connection-related
        instance variables to allow for fresh connections.
        """
        if self._session:
            await self._session.close()
            self._session = None
            self._initialized = False
            self._session_id = None
            self._messages_url = None


# Global MCP client instance - using HTTP SSE
mcp_client = MCPSSEClient(
    sse_url=os.getenv("JIRA_MCP_SSE_URL", "https://jira-mcp-snowflake.mcp-playground-poc.devshift.net/sse"),
    snowflake_token=os.getenv("JIRA_MCP_SNOWFLAKE_TOKEN", "")
)


async def call_mcp_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """Call a tool on the JIRA MCP server using the global MCP client.

    This is a convenience function that wraps the global mcp_client.call_tool method
    with additional error handling and logging.

    Args:
        tool_name: Name of the MCP tool to call (e.g., 'list_jira_issues')
        **kwargs: Arguments to pass to the tool

    Returns:
        dict: Result from the MCP server
        
    Raises:
        Exception: Re-raises any exceptions from the underlying MCP client
    """
    print(f"DEBUG: call_mcp_tool starting for {tool_name} with kwargs: {kwargs}")
    try:
        result = await mcp_client.call_tool(tool_name, **kwargs)
        print(f"DEBUG: call_mcp_tool completed for {tool_name}")
        return result
    except Exception as e:
        print(f"DEBUG: call_mcp_tool failed for {tool_name}: {e}")
        raise


class JIRAMCPToolset:
    """Toolset wrapper for managing and discovering JIRA MCP tools.
    
    This class provides a higher-level interface for interacting with the MCP server's
    available tools, including dynamic tool discovery and wrapper creation.
    """

    def __init__(self, client):
        self.client = client

    async def get_tools(self):
        """Discover and retrieve available tools from the MCP server.
        
        Returns:
            list[JIRAMCPTool]: List of available tool wrappers, empty list on error
        """
        try:
            await self.client._ensure_connection()

            # List tools request
            tools_request = {
                "jsonrpc": "2.0",
                "id": self.client._get_next_id(),
                "method": "tools/list",
                "params": {}
            }

            response = await self.client._send_http_request(tools_request)

            if "result" in response and "tools" in response["result"]:
                # Convert to simple tool objects with call method
                tools = []
                for tool_info in response["result"]["tools"]:
                    tool = JIRAMCPTool(tool_info["name"], self.client)
                    tools.append(tool)
                return tools
            else:
                return []

        except Exception as e:
            print(f"Error getting tools: {e}")
            return []


class JIRAMCPTool:
    """Wrapper for individual JIRA MCP tools.
    
    Provides a simple interface for calling specific MCP tools by name.
    """

    def __init__(self, name: str, client):
        self.name = name
        self.client = client

    async def call(self, **kwargs):
        """Call this tool with the given arguments.
        
        Args:
            **kwargs: Arguments to pass to the underlying MCP tool
            
        Returns:
            dict: Result from the MCP server
        """
        return await self.client.call_tool(self.name, **kwargs)


# Global toolset instance
jira_mcp_toolset = JIRAMCPToolset(mcp_client)




async def list_jira_issues(
    project: Optional[str] = None,
    issue_keys: Optional[List[str]] = None,
    issue_type: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    search_text: Optional[str] = None,
    timeframe: int = 0,
    components: Optional[str] = None,
    created_days: int = 0,
    updated_days: int = 0,
    resolved_days: int = 0,
    fixed_version: Optional[str] = None,
    affected_version: Optional[str] = None,
) -> Dict[str, Any]:
    """List JIRA issues from Snowflake database with comprehensive filtering options.
    
    This function queries the JIRA data stored in Snowflake using the MCP server,
    allowing for complex filtering and searching across multiple issue attributes.
    
    Args:
        project: Filter by project key (e.g., 'SMQE', 'OSIM')
        issue_keys: List of specific JIRA issue keys (e.g., ['SMQE-1280', 'SMQE-1281'])
        issue_type: Filter by issue type ID (numeric)
        status: Filter by issue status ID (numeric) 
        priority: Filter by priority ID (numeric)
        limit: Maximum number of issues to return (default: 50)
        search_text: Text search in summary and description fields
        timeframe: Filter issues where ANY date is within last N days (0 = disabled)
        components: Comma-separated component names; matches ANY component
        created_days: Filter by creation date within last N days (0 = disabled)
        updated_days: Filter by update date within last N days (0 = disabled)
        resolved_days: Filter by resolution date within last N days (0 = disabled)
        fixed_version: Filter by fixed/target version name (exact match)
        affected_version: Filter by affected version name (exact match)
        
    Returns:
        dict: Dictionary containing 'issues' list and metadata, or error information
    """
    try:
        result = await call_mcp_tool(
            "list_jira_issues",
            project=project,
            issue_keys=issue_keys,
            issue_type=issue_type,
            status=status,
            priority=priority,
            limit=limit,
            search_text=search_text,
            timeframe=timeframe,
            components=components,
            created_days=created_days,
            updated_days=updated_days,
            resolved_days=resolved_days,
            fixed_version=fixed_version,
            affected_version=affected_version
        )
        return result
    except Exception as e:
        return {"error": f"Error listing JIRA issues: {str(e)}", "issues": []}


async def get_jira_issue_details(issue_keys: List[str]) -> Dict[str, Any]:
    """Get comprehensive detailed information for multiple JIRA issues.

    Retrieves full issue details including descriptions, comments, custom fields,
    attachments, and other metadata for the specified issue keys.

    Args:
        issue_keys: List of JIRA issue keys (e.g., ['SMQE-1280', 'SMQE-1281'])

    Returns:
        dict: Dictionary containing detailed issue information including comments,
              or error information if the request fails or times out
    """
    try:
        print(f"DEBUG: Starting get_jira_issue_details for {issue_keys}")

        # Add timeout protection
        result = await asyncio.wait_for(
            call_mcp_tool("get_jira_issue_details", issue_keys=issue_keys),
            timeout=30.0  # 30 second timeout
        )

        print(f"DEBUG: get_jira_issue_details completed with result type: {type(result)}")
        return result
    except asyncio.TimeoutError:
        print("DEBUG: get_jira_issue_details timed out")
        return {"error": "Request timed out after 30 seconds", "issue_keys": issue_keys}
    except Exception as e:
        print(f"DEBUG: get_jira_issue_details failed with exception: {e}")
        return {"error": f"Error getting JIRA issue details: {str(e)}"}


async def get_jira_project_summary() -> Dict[str, Any]:
    """Get statistical summary of all JIRA projects in the Snowflake database.
    
    Provides overview statistics including issue counts, project keys, and
    other aggregated metrics across all available JIRA projects.
    
    Returns:
        dict: Dictionary containing project statistics and metadata,
              or error information if the request fails
    """
    try:
        result = await call_mcp_tool("get_jira_project_summary")
        return result
    except Exception as e:
        return {"error": f"Error getting JIRA project summary: {str(e)}"}


async def get_jira_issue_links(issue_key: str) -> Dict[str, Any]:
    """Get issue links and relationships for a specific JIRA issue.

    Retrieves all linked issues, including blocks/blocked by, relates to,
    duplicates, and other relationship types for the specified issue.

    Args:
        issue_key: The JIRA issue key (e.g., 'SMQE-1280')

    Returns:
        dict: Dictionary containing issue links information and relationship types,
              or error information if the request fails
    """
    try:
        result = await call_mcp_tool(
            "get_jira_issue_links",
            issue_key=issue_key
        )
        return result
    except Exception as e:
        return {"error": f"Error getting JIRA issue links: {str(e)}"}


async def get_jira_sprint_details(sprint_name: Optional[List[str]] = None, project: Optional[str] = None, board_id: Optional[int] = None, sprint_state: Optional[str] = None) -> Dict[str, Any]:
    """Get detailed JIRA sprint information from Snowflake database.

    Retrieves sprint details including start/end dates, goals, issue counts,
    and other sprint-related metadata based on the specified filters.

    Args:
        sprint_name: List of specific sprint names to retrieve (e.g., ['Sprint 1', 'Sprint 2'])
        project: Filter by project key (e.g., 'SMQE', 'OSIM')
        board_id: Filter by specific board ID (numeric)
        sprint_state: Filter by sprint state ('active', 'closed', 'future')

    Returns:
        dict: Dictionary containing sprint information, issue assignments, and metrics,
              or error information if the request fails
    """
    try:
        result = await call_mcp_tool(
            "get_jira_sprint_details",
            sprint_name=sprint_name,
            project=project,
            board_id=board_id,
            sprint_state=sprint_state
        )
        return result
    except Exception as e:
        return {"error": f"Error getting JIRA sprint details: {str(e)}"}


root_agent = Agent(
    name="jira_mcp_snowflake_agent",
    model="gemini-2.5-flash",
    description=(
        "Specialized agent for analyzing and retrieving JIRA data from Snowflake database. "
        "Provides comprehensive access to issues, projects, sprints, and relationships through "
        "MCP (Model Context Protocol) integration."
    ),
    instruction=(
        "You are a helpful agent specialized in analyzing and retrieving JIRA data stored in Snowflake. "
        "You can help users search for issues, get detailed issue information including comments, "
        "view project summaries and statistics, explore issue links and relationships, and analyze "
        "sprint details. Use the available JIRA tools to answer questions about projects, issues, "
        "sprints, and their relationships. You can filter by various criteria like project, status, "
        "priority, components, versions, and time ranges to provide targeted insights."
    ),
    tools=[
        list_jira_issues,
        get_jira_issue_details,
        get_jira_project_summary,
        get_jira_issue_links,
        get_jira_sprint_details
    ],
)