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
import mimetypes
import re

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
    
    def add_document(self, content: str, filename: str, source: str = "rag_server") -> Dict[str, Any]:
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
            success = self.doc_manager.add_document(
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
    
    def analyze_document(self, filename: str) -> Dict[str, Any]:
        """Analyze document structure, format, and extract metadata"""
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
            
            # Analyze document
            analysis = self._analyze_content(content, filename)
            
            return {
                "success": True,
                "filename": filename,
                "analysis": analysis,
                "metadata": found_doc
            }
            
        except Exception as e:
            print(f"[RAG] Error analyzing document {filename}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"Error analyzing document: {str(e)}"
            }
    
    def _analyze_content(self, content: str, filename: str) -> Dict[str, Any]:
        """Analyze document content and extract insights"""
        try:
            # Detect document format
            file_ext = Path(filename).suffix.lower()
            format_info = self._detect_format(file_ext, content)
            
            # Extract structure
            structure = self._extract_structure(content, format_info["type"])
            
            # Extract key topics/keywords
            topics = self._extract_topics(content)
            
            # Extract entities (simple regex-based)
            entities = self._extract_entities(content)
            
            # Calculate readability metrics
            readability = self._calculate_readability(content)
            
            return {
                "format": format_info,
                "structure": structure,
                "topics": topics,
                "entities": entities,
                "readability": readability,
                "stats": {
                    "char_count": len(content),
                    "word_count": len(content.split()),
                    "line_count": len(content.splitlines()),
                    "paragraph_count": len([p for p in content.split('\n\n') if p.strip()])
                }
            }
            
        except Exception as e:
            print(f"[RAG] Error analyzing content: {e}")
            return {"error": str(e)}
    
    def _detect_format(self, file_ext: str, content: str) -> Dict[str, Any]:
        """Detect document format and type"""
        format_map = {
            '.txt': {'type': 'text', 'description': 'Plain text document'},
            '.md': {'type': 'markdown', 'description': 'Markdown document'},
            '.py': {'type': 'code', 'description': 'Python source code'},
            '.js': {'type': 'code', 'description': 'JavaScript source code'},
            '.html': {'type': 'markup', 'description': 'HTML document'},
            '.xml': {'type': 'markup', 'description': 'XML document'},
            '.json': {'type': 'data', 'description': 'JSON data file'},
            '.csv': {'type': 'data', 'description': 'CSV data file'},
            '.log': {'type': 'log', 'description': 'Log file'},
            '.conf': {'type': 'config', 'description': 'Configuration file'},
            '.yml': {'type': 'config', 'description': 'YAML configuration'},
            '.yaml': {'type': 'config', 'description': 'YAML configuration'},
        }
        
        base_format = format_map.get(file_ext, {'type': 'unknown', 'description': 'Unknown format'})
        
        # Additional content-based detection
        if content.startswith('#') and '\n' in content:
            base_format['subtype'] = 'markdown'
        elif content.startswith('<!DOCTYPE') or content.startswith('<html'):
            base_format['subtype'] = 'html'
        elif content.startswith('<?xml'):
            base_format['subtype'] = 'xml'
        elif '{' in content and '}' in content:
            try:
                json.loads(content)
                base_format['subtype'] = 'json'
            except:
                pass
        
        return base_format
    
    def _extract_structure(self, content: str, doc_type: str) -> Dict[str, Any]:
        """Extract document structure based on type"""
        structure = {
            "headings": [],
            "sections": [],
            "lists": [],
            "code_blocks": [],
            "tables": []
        }
        
        lines = content.splitlines()
        
        # Extract headings (markdown-style)
        for i, line in enumerate(lines):
            if line.startswith('#'):
                level = len(line) - len(line.lstrip('#'))
                heading = line.lstrip('# ').strip()
                structure["headings"].append({
                    "level": level,
                    "text": heading,
                    "line": i + 1
                })
        
        # Extract code blocks
        in_code_block = False
        code_block = []
        for i, line in enumerate(lines):
            if line.strip().startswith('```'):
                if in_code_block:
                    structure["code_blocks"].append({
                        "content": '\n'.join(code_block),
                        "start_line": code_start,
                        "end_line": i + 1
                    })
                    code_block = []
                    in_code_block = False
                else:
                    code_start = i + 1
                    in_code_block = True
            elif in_code_block:
                code_block.append(line)
        
        # Extract lists
        for i, line in enumerate(lines):
            if line.strip().startswith(('-', '*', '+')):
                structure["lists"].append({
                    "text": line.strip(),
                    "line": i + 1
                })
        
        return structure
    
    def _extract_topics(self, content: str) -> List[str]:
        """Extract key topics/keywords from content"""
        # Simple keyword extraction (can be enhanced with NLP libraries)
        words = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())
        
        # Common stop words to filter out
        stop_words = {
            'this', 'that', 'with', 'have', 'will', 'from', 'they', 'been', 'were',
            'said', 'each', 'which', 'their', 'time', 'would', 'there', 'could',
            'other', 'after', 'first', 'well', 'also', 'new', 'want', 'because',
            'any', 'these', 'give', 'day', 'may', 'say', 'use', 'her', 'many',
            'some', 'very', 'when', 'much', 'then', 'them', 'can', 'only', 'over',
            'think', 'also', 'back', 'where', 'much', 'before', 'move', 'right',
            'boy', 'old', 'too', 'same', 'she', 'all', 'there', 'when', 'up',
            'time', 'very', 'what', 'know', 'just', 'first', 'get', 'over', 'think',
            'go', 'no', 'way', 'could', 'people', 'my', 'than', 'into', 'has',
            'more', 'her', 'two', 'like', 'him', 'see', 'time', 'could', 'no',
            'make', 'than', 'first', 'been', 'call', 'who', 'its', 'now', 'find',
            'long', 'down', 'day', 'did', 'get', 'come', 'made', 'may', 'part'
        }
        
        # Count word frequency
        word_count = {}
        for word in words:
            if word not in stop_words and len(word) > 3:
                word_count[word] = word_count.get(word, 0) + 1
        
        # Return top 10 most frequent words
        topics = sorted(word_count.items(), key=lambda x: x[1], reverse=True)[:10]
        return [topic[0] for topic in topics]
    
    def _extract_entities(self, content: str) -> Dict[str, List[str]]:
        """Extract entities from content (simple regex-based)"""
        entities = {
            "emails": [],
            "urls": [],
            "phone_numbers": [],
            "dates": [],
            "numbers": []
        }
        
        # Extract emails
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["emails"] = re.findall(email_pattern, content)
        
        # Extract URLs
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        entities["urls"] = re.findall(url_pattern, content)
        
        # Extract phone numbers (simple pattern)
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        entities["phone_numbers"] = re.findall(phone_pattern, content)
        
        # Extract dates (simple patterns)
        date_patterns = [
            r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
            r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b',
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}\b'
        ]
        for pattern in date_patterns:
            entities["dates"].extend(re.findall(pattern, content, re.IGNORECASE))
        
        # Extract numbers
        number_pattern = r'\b\d+(?:\.\d+)?\b'
        entities["numbers"] = re.findall(number_pattern, content)
        
        return entities
    
    def _calculate_readability(self, content: str) -> Dict[str, Any]:
        """Calculate basic readability metrics"""
        sentences = re.split(r'[.!?]+', content)
        words = content.split()
        
        if len(sentences) == 0 or len(words) == 0:
            return {"error": "Cannot calculate readability for empty content"}
        
        avg_words_per_sentence = len(words) / len(sentences)
        avg_chars_per_word = sum(len(word) for word in words) / len(words)
        
        # Simple readability score (0-100, higher is easier)
        readability_score = max(0, min(100, 100 - (avg_words_per_sentence * 1.5) - (avg_chars_per_word * 2)))
        
        return {
            "score": round(readability_score, 1),
            "level": "Easy" if readability_score > 70 else "Medium" if readability_score > 50 else "Hard",
            "avg_words_per_sentence": round(avg_words_per_sentence, 1),
            "avg_chars_per_word": round(avg_chars_per_word, 1),
            "total_sentences": len(sentences),
            "total_words": len(words)
        }
    
    def query_documents(self, query: str, n_results: int = 3) -> Dict[str, Any]:
        """Query documents in the RAG database"""
        try:
            if not self.doc_manager:
                return {
                    "success": False,
                    "error": "Document manager not available",
                    "results": []
                }
            
            print(f"[RAG] Querying documents for: {query}")
            
            results = self.doc_manager.query_documents(query, n_results=n_results)
            
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
                name="analyze_document",
                description="Analyze document structure, format, and extract metadata (netrunner-style document analysis)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Document filename to analyze"
                        }
                    },
                    "required": ["filename"]
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
                result = rag_server.add_document(
                    content=arguments.get("content", ""),
                    filename=arguments.get("filename", "untitled.txt"),
                    source=arguments.get("source", "rag_server")
                )
                return CallToolResult(
                    content=[TextContent(type="text", text=json.dumps(result, indent=2))]
                )
            
            elif name == "query_documents":
                result = rag_server.query_documents(
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
            
            elif name == "analyze_document":
                result = rag_server.analyze_document(
                    filename=arguments.get("filename", "")
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
def add_document(content: str, filename: str, source: str = "rag_server") -> Dict[str, Any]:
    """Add a document to the RAG database"""
    return rag_server.add_document(content, filename, source)

def query_documents(query: str, n_results: int = 3) -> Dict[str, Any]:
    """Query documents in the RAG database"""
    return rag_server.query_documents(query, n_results)

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

def analyze_document(filename: str) -> Dict[str, Any]:
    """Analyze document structure, format, and extract metadata (netrunner-style)"""
    return rag_server.analyze_document(filename)

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
