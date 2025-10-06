#!/usr/bin/env python3
"""
RAG MCP Server for DecypherTek AI
Provides document management and retrieval capabilities
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib
import time

# Try to import MCP server components
try:
    from mcp.server import Server
    from mcp.types import (
        Tool, TextContent, CallToolResult, ErrorData,
    )
    MCP_AVAILABLE = True
    app = Server("rag")
except ImportError:
    MCP_AVAILABLE = False
    print("[RAG] MCP server not available - running in standalone mode")

# Add the src directory to the path to import DocumentManager
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

try:
    from rag.document_manager import DocumentManager
    RAG_AVAILABLE = True
except ImportError as e:
    RAG_AVAILABLE = False
    print(f"[RAG] DocumentManager not available: {e}")

class RAGServer:
    """RAG server for document management and retrieval"""
    
    def __init__(self):
        self.doc_manager = None
        self.storage_dir = Path.home() / ".decyphertek-ai"
        self._init_document_manager()
    
    def _init_document_manager(self):
        """Initialize the document manager"""
        try:
            if RAG_AVAILABLE:
                # Try to get OpenRouter API key from environment or config
                api_key = None
                # You might want to load this from a config file
                self.doc_manager = DocumentManager(str(self.storage_dir), openrouter_api_key=api_key)
                print(f"[RAG] Document manager initialized at {self.storage_dir}")
            else:
                print("[RAG] DocumentManager not available - RAG features disabled")
        except Exception as e:
            print(f"[RAG] Error initializing document manager: {e}")
            self.doc_manager = None
    
    async def add_document(self, content: str, filename: str, source: str = "rag_server") -> Dict[str, Any]:
        """Add a document to the RAG database with complete processing"""
        try:
            if not self.doc_manager:
                return {
                    "success": False,
                    "error": "Document manager not available",
                    "message": "RAG system not initialized"
                }
            
            print(f"[RAG] Processing document: {filename} ({len(content)} chars)")
            
            # Add document (DocumentManager now handles unique ID generation)
            success = await self.doc_manager.add_document(
                content=content,
                filename=filename,
                source=source
            )
            
            if success:
                # Get document info after successful addition
                documents = self.doc_manager.get_documents()
                doc_info = None
                for doc_id, info in documents.items():
                    if info.get('filename') == filename:
                        doc_info = info
                        break
                
                result = {
                    "success": True,
                    "filename": filename,
                    "size": len(content),
                    "source": source,
                    "message": f"Document '{filename}' processed and added to RAG database",
                    "status": "processed_and_stored"
                }
                
                if doc_info:
                    result.update({
                        "doc_id": doc_id,
                        "chunks": doc_info.get('chunks', 0),
                        "storage_location": str(self.storage_dir / "qdrant"),
                        "metadata_file": str(self.storage_dir / "documents.json")
                    })
                
                print(f"[RAG] Document {filename} successfully processed and stored")
                return result
            else:
                return {
                    "success": False,
                    "error": "Document processing failed",
                    "message": f"Document '{filename}' could not be processed or already exists"
                }
                
        except Exception as e:
            print(f"[RAG] Error processing document {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error processing document: {str(e)}"
            }
    
    def read_document(self, filename: str) -> Dict[str, Any]:
        """Read a specific document from storage"""
        try:
            # Load documents metadata
            docs_metadata_file = self.storage_dir / "documents.json"
            if not docs_metadata_file.exists():
                return {
                    "success": False,
                    "error": "No documents found",
                    "message": "No documents have been uploaded yet"
                }
            
            documents = json.loads(docs_metadata_file.read_text(encoding="utf-8"))
            
            # Find document by original filename
            found_doc = None
            for stored_filename, doc_info in documents.items():
                if doc_info.get("original_filename") == filename:
                    found_doc = doc_info
                    break
            
            if not found_doc:
                return {
                    "success": False,
                    "error": "Document not found",
                    "message": f"Document '{filename}' not found in storage"
                }
            
            # Read document content
            file_path = Path(found_doc["file_path"])
            if not file_path.exists():
                return {
                    "success": False,
                    "error": "File not found",
                    "message": f"Document file not found at {file_path}"
                }
            
            content = file_path.read_text(encoding="utf-8")
            
            return {
                "success": True,
                "filename": filename,
                "content": content,
                "size": len(content),
                "uploaded_at": found_doc.get("uploaded_at"),
                "source": found_doc.get("source", "unknown")
            }
            
        except Exception as e:
            print(f"[RAG] Error reading document {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error reading document: {str(e)}"
            }
    
    def search_documents(self, query: str) -> Dict[str, Any]:
        """Search through stored documents by content"""
        try:
            # Load documents metadata
            docs_metadata_file = self.storage_dir / "documents.json"
            if not docs_metadata_file.exists():
                return {
                    "success": False,
                    "error": "No documents found",
                    "message": "No documents have been uploaded yet"
                }
            
            documents = json.loads(docs_metadata_file.read_text(encoding="utf-8"))
            
            results = []
            query_lower = query.lower()
            
            # Search through all documents
            for stored_filename, doc_info in documents.items():
                try:
                    file_path = Path(doc_info["file_path"])
                    if file_path.exists():
                        content = file_path.read_text(encoding="utf-8")
                        
                        # Simple text search
                        if query_lower in content.lower():
                            # Find context around the match
                            content_lower = content.lower()
                            match_index = content_lower.find(query_lower)
                            
                            # Get context (100 chars before and after)
                            start = max(0, match_index - 100)
                            end = min(len(content), match_index + len(query) + 100)
                            context = content[start:end]
                            
                            results.append({
                                "filename": doc_info["original_filename"],
                                "stored_filename": stored_filename,
                                "context": context,
                                "match_position": match_index,
                                "size": len(content),
                                "uploaded_at": doc_info.get("uploaded_at")
                            })
                            
                except Exception as e:
                    print(f"[RAG] Error reading document {doc_info.get('original_filename', stored_filename)}: {e}")
                    continue
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "total_matches": len(results)
            }
            
        except Exception as e:
            print(f"[RAG] Error searching documents: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error searching documents: {str(e)}"
            }
    
    async def query_documents(self, query: str, n_results: int = 3) -> Dict[str, Any]:
        """Query documents in the RAG database"""
        try:
            if not self.doc_manager:
                return {
                    "success": False,
                    "error": "Document manager not available",
                    "results": []
                }
            
            print(f"[RAG] Querying documents for: {query}")
            
            results = await self.doc_manager.query_documents(query, n_results=n_results)
            
            return {
                "success": True,
                "query": query,
                "results": results,
                "count": len(results)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "results": []
            }
    
    def list_documents(self) -> Dict[str, Any]:
        """List all documents in the RAG database"""
        try:
            if not self.doc_manager:
                return {
                    "success": False,
                    "error": "Document manager not available",
                    "documents": []
                }
            
            documents = self.doc_manager.get_documents()
            
            return {
                "success": True,
                "documents": documents,
                "count": len(documents)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "documents": []
            }
    
    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        """Delete a document from the RAG database"""
        try:
            if not self.doc_manager:
                return {
                    "success": False,
                    "error": "Document manager not available"
                }
            
            success = self.doc_manager.delete_document(doc_id)
            
            if success:
                return {
                    "success": True,
                    "message": f"Document {doc_id} deleted successfully"
                }
            else:
                return {
                    "success": False,
                    "error": f"Document {doc_id} not found"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

# Initialize RAG server
rag_server = RAGServer()

# MCP Server functions (only if MCP is available)
if MCP_AVAILABLE:
    @app.list_tools()
    async def list_tools() -> List[Tool]:
        """List available RAG tools"""
        return [
            Tool(
                name="add_document",
                description="Add a document to the RAG database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Document content"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Document filename"
                        },
                        "source": {
                            "type": "string",
                            "description": "Document source (default: rag_server)",
                            "default": "rag_server"
                        }
                    },
                    "required": ["content", "filename"]
                }
            ),
            Tool(
                name="query_documents",
                description="Query documents in the RAG database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "n_results": {
                            "type": "integer",
                            "description": "Number of results to return (default: 3)",
                            "default": 3
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="list_documents",
                description="List all documents in the RAG database",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="read_document",
                description="Read a specific document from storage",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Document filename to read"
                        }
                    },
                    "required": ["filename"]
                }
            ),
            Tool(
                name="search_documents",
                description="Search through stored documents by content",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find in document content"
                        }
                    },
                    "required": ["query"]
                }
            ),
            Tool(
                name="delete_document",
                description="Delete a document from the RAG database",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "Document ID to delete"
                        }
                    },
                    "required": ["doc_id"]
                }
            )
        ]
    
    @app.call_tool()
    async def call_tool(name: str, arguments: Any) -> CallToolResult:
        """Execute RAG tool calls"""
        try:
            if name == "add_document":
                result = await rag_server.add_document(
                    content=arguments.get("content", ""),
                    filename=arguments.get("filename", "untitled.txt"),
                    source=arguments.get("source", "rag_server")
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            elif name == "query_documents":
                result = await rag_server.query_documents(
                    query=arguments.get("query", ""),
                    n_results=arguments.get("n_results", 3)
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            elif name == "list_documents":
                result = rag_server.list_documents()
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            elif name == "delete_document":
                result = rag_server.delete_document(
                    doc_id=arguments.get("doc_id", "")
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            elif name == "read_document":
                result = rag_server.read_document(
                    filename=arguments.get("filename", "")
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            elif name == "search_documents":
                result = rag_server.search_documents(
                    query=arguments.get("query", "")
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            else:
                return CallToolResult(
                    content=[TextContent(type="text", text=f"Unknown tool: {name}")],
                    isError=True
                )
                
        except Exception as e:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Error: {str(e)}")],
                isError=True
            )

# Standalone functions for direct import
async def add_document(content: str, filename: str, source: str = "rag_server") -> Dict[str, Any]:
    """Add a document to the RAG database"""
    return await rag_server.add_document(content, filename, source)

async def query_documents(query: str, n_results: int = 3) -> Dict[str, Any]:
    """Query documents in the RAG database"""
    return await rag_server.query_documents(query, n_results)

def list_documents() -> Dict[str, Any]:
    """List all documents in the RAG database"""
    return rag_server.list_documents()

def delete_document(doc_id: str) -> Dict[str, Any]:
    """Delete a document from the RAG database"""
    return rag_server.delete_document(doc_id)

def read_document(filename: str) -> Dict[str, Any]:
    """Read a specific document from storage"""
    return rag_server.read_document(filename)

def search_documents(query: str) -> Dict[str, Any]:
    """Search through stored documents by content"""
    return rag_server.search_documents(query)

async def main():
    """Main function for MCP server"""
    if MCP_AVAILABLE:
        from mcp.server.stdio import stdio_server
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )

if __name__ == "__main__":
    if MCP_AVAILABLE:
        asyncio.run(main())
    else:
        # Standalone mode - can be imported and used directly
        print("[RAG] Running in standalone mode - ready for import")
