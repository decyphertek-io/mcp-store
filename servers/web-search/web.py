#!/usr/bin/env python3
"""
Web Search MCP Server
A production-ready MCP server providing web search functionality with multiple fallback methods.
"""

import asyncio
import json
import os
import sys
from typing import List, Dict, Any

# Debug mode controlled by environment variable
DEBUG_MODE = os.environ.get("MCP_DEBUG", "0").lower() in ("1", "true", "yes")

def debug_print(msg: str):
    """Print debug messages only when DEBUG_MODE is enabled"""
    if DEBUG_MODE:
        print(f"[Web Search Debug] {msg}", flush=True)

# Try to import required libraries
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
    debug_print("✅ duckduckgo_search imported successfully")
except ImportError as e:
    DDGS_AVAILABLE = False
    debug_print(f"❌ duckduckgo_search import failed: {e}")

try:
    import requests
from bs4 import BeautifulSoup
    REQUESTS_AVAILABLE = True
    BS4_AVAILABLE = True
    debug_print("✅ requests and beautifulsoup4 imported successfully")
except ImportError as e:
    REQUESTS_AVAILABLE = False
    BS4_AVAILABLE = False
    debug_print(f"❌ requests/bs4 import failed: {e}")

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent, CallToolResult
    from mcp.server.stdio import stdio_server
    MCP_AVAILABLE = True
    debug_print("✅ MCP SDK imported successfully")
except ImportError as e:
    MCP_AVAILABLE = False
    debug_print(f"❌ MCP SDK import failed: {e}")


def search_duckduckgo_api(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using DuckDuckGo API (primary method)"""
    if not DDGS_AVAILABLE:
        debug_print("DuckDuckGo API unavailable (library not installed)")
        return []
    
    try:
        debug_print(f"Attempting DuckDuckGo API search for: '{query}'")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        
        formatted = []
        for r in results:
            formatted.append({
                'title': r.get('title', 'No title'),
                'url': r.get('href', ''),
                'snippet': r.get('body', 'No description')
            })
        
        debug_print(f"✅ DuckDuckGo API returned {len(formatted)} results")
        return formatted
    except Exception as e:
        debug_print(f"❌ DuckDuckGo API error: {e}")
        return []


def search_duckduckgo_html(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using DuckDuckGo HTML scraping (fallback 1)"""
    if not (REQUESTS_AVAILABLE and BS4_AVAILABLE):
        debug_print("DuckDuckGo HTML unavailable (requests/bs4 not installed)")
        return []
    
    try:
        debug_print(f"Attempting DuckDuckGo HTML search for: '{query}'")
        import urllib.parse
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        for result in soup.select('.result')[:max_results]:
            title_elem = result.select_one('.result__title')
            link_elem = result.select_one('.result__url')
            snippet_elem = result.select_one('.result__snippet')
                
                if title_elem and link_elem:
                    results.append({
                    'title': title_elem.get_text(strip=True),
                    'url': f"https:{link_elem.get('href', '')}" if link_elem.get('href', '').startswith('//') else link_elem.get('href', ''),
                    'snippet': snippet_elem.get_text(strip=True) if snippet_elem else 'No description'
                })
        
        debug_print(f"✅ DuckDuckGo HTML returned {len(results)} results")
        return results
    except Exception as e:
        debug_print(f"❌ DuckDuckGo HTML error: {e}")
        return []


def search_bing_html(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Search using Bing HTML scraping (fallback 2)"""
    if not (REQUESTS_AVAILABLE and BS4_AVAILABLE):
        debug_print("Bing HTML unavailable (requests/bs4 not installed)")
        return []
    
    try:
        debug_print(f"Attempting Bing HTML search for: '{query}'")
        import urllib.parse
        url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        results = []
        
        for result in soup.select('.b_algo')[:max_results]:
            title_elem = result.select_one('h2 a')
            snippet_elem = result.select_one('.b_caption p')
                
                if title_elem:
                    results.append({
                    'title': title_elem.get_text(strip=True),
                    'url': title_elem.get('href', ''),
                    'snippet': snippet_elem.get_text(strip=True) if snippet_elem else 'No description'
                })
        
        debug_print(f"✅ Bing HTML returned {len(results)} results")
        return results
    except Exception as e:
        debug_print(f"❌ Bing HTML error: {e}")
        return []


def search_with_fallbacks(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Execute web search with multiple fallback methods.
    Tries methods in order until one succeeds.
    """
    debug_print(f"=== Starting web search for: '{query}' ===")
    debug_print(f"Python: {sys.executable}")
    debug_print(f"Libraries: DDGS={DDGS_AVAILABLE}, requests={REQUESTS_AVAILABLE}, bs4={BS4_AVAILABLE}")
    
    # Try each method in order
    methods = [
        ("DuckDuckGo API", search_duckduckgo_api),
        ("DuckDuckGo HTML", search_duckduckgo_html),
        ("Bing HTML", search_bing_html)
    ]
    
    for method_name, method_func in methods:
        debug_print(f"Trying {method_name}...")
        results = method_func(query, max_results)
            if results:
            debug_print(f"✅ {method_name} succeeded with {len(results)} results")
            return results
    
    debug_print("❌ All search methods failed")
    return []


def format_results(results: List[Dict[str, str]]) -> str:
    """Format search results as clean text"""
    if not results:
        return "No results found. All search methods failed. This may be due to:\n" \
               "- Missing dependencies (duckduckgo-search, requests, beautifulsoup4)\n" \
               "- Network connectivity issues\n" \
               "- Rate limiting from search engines"
    
    lines = []
    for i, result in enumerate(results, 1):
        lines.append(f"{i}. **{result['title']}**")
        lines.append(f"   {result['snippet']}")
        lines.append(f"   {result['url']}\n")
    
    return "\n".join(lines)


# ============================================================================
# MCP Server Implementation
# ============================================================================

if MCP_AVAILABLE:
    app = Server("web-search")
    
    @app.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools"""
        return [
            Tool(
                name="web_search",
                description="Search the web for information using DuckDuckGo and other search engines",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 5)",
                            "default": 5
                        }
                    },
                    "required": ["query"]
                }
            )
        ]
    
    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> CallToolResult:
        """Handle tool calls"""
        if name != "web_search":
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                isError=True
            )
        
    query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        
        if not query:
            return CallToolResult(
                content=[TextContent(type="text", text="Error: query parameter is required")],
                isError=True
            )
        
        # Perform search
        results = search_with_fallbacks(query, max_results)
        formatted = format_results(results)
        
        return CallToolResult(
            content=[TextContent(type="text", text=formatted)],
            isError=False
        )


# ============================================================================
# Entry Point
# ============================================================================

    async def main():
    """Main entry point for MCP server"""
    if not MCP_AVAILABLE:
        print(json.dumps({
            "error": "MCP SDK not available",
            "details": "Install with: pip install mcp"
        }))
        return
    
        async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    if MCP_AVAILABLE:
        # Run as MCP server
        asyncio.run(main())
    else:
        # Standalone mode - read JSON from stdin
        try:
            input_data = json.loads(sys.stdin.read())
            query = input_data.get("message", "")
            max_results = input_data.get("max_results", 5)
            
            results = search_with_fallbacks(query, max_results)
            formatted = format_results(results)
            
            print(json.dumps({"text": formatted, "status": "success"}))
        except Exception as e:
            print(json.dumps({"text": f"Error: {e}", "status": "error"}))

