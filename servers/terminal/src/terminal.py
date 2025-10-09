#!/usr/bin/env python3
"""
Terminal MCP Server
Provides secure terminal access to allowed directories for running commands.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional
import subprocess
import shlex

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

# Load configuration
def load_config() -> dict:
    """Load terminal configuration from terminal.config file."""
    config_path = Path(__file__).parent.parent / "terminal.config"
    
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            return {}
    else:
        print(f"Config file not found at {config_path}", file=sys.stderr)
        return {}

# Initialize configuration
CONFIG = load_config()
ALLOWED_DIRS = CONFIG.get("allowed_directories", [])
DEFAULT_SHELL = CONFIG.get("default_shell", "/bin/bash")
MAX_OUTPUT_LENGTH = CONFIG.get("max_output_length", 10000)
TIMEOUT = CONFIG.get("command_timeout", 300)  # 5 minutes default

def is_path_allowed(path: str) -> bool:
    """Check if a path is within allowed directories."""
    try:
        abs_path = Path(path).resolve()
        for allowed_dir in ALLOWED_DIRS:
            allowed_path = Path(allowed_dir).resolve()
            try:
                abs_path.relative_to(allowed_path)
                return True
            except ValueError:
                continue
        return False
    except Exception:
        return False

def get_allowed_working_dir(requested_dir: Optional[str] = None) -> str:
    """Get a valid working directory from request or default to first allowed dir."""
    if requested_dir:
        if is_path_allowed(requested_dir):
            return str(Path(requested_dir).resolve())
        else:
            raise ValueError(f"Directory not allowed: {requested_dir}")
    
    if ALLOWED_DIRS:
        return str(Path(ALLOWED_DIRS[0]).resolve())
    
    raise ValueError("No allowed directories configured")

async def run_command(
    command: str,
    working_dir: Optional[str] = None,
    shell: bool = True,
    env: Optional[dict] = None
) -> dict:
    """
    Execute a command and return the result.
    
    Args:
        command: Command to execute
        working_dir: Working directory for command execution
        shell: Whether to run command in shell
        env: Additional environment variables
    
    Returns:
        Dict with stdout, stderr, exit_code, and working_dir
    """
    try:
        # Get and validate working directory
        cwd = get_allowed_working_dir(working_dir)
        
        # Prepare environment
        cmd_env = os.environ.copy()
        if env:
            cmd_env.update(env)
        
        # Execute command
        if shell:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env,
                shell=True,
                executable=DEFAULT_SHELL
            )
        else:
            # For non-shell execution, split the command
            cmd_parts = shlex.split(command)
            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
                env=cmd_env
            )
        
        # Wait for command with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=TIMEOUT
            )
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return {
                "stdout": "",
                "stderr": f"Command timed out after {TIMEOUT} seconds",
                "exit_code": -1,
                "working_dir": cwd,
                "error": "timeout"
            }
        
        # Decode output
        stdout_text = stdout.decode('utf-8', errors='replace')
        stderr_text = stderr.decode('utf-8', errors='replace')
        
        # Truncate if necessary
        if len(stdout_text) > MAX_OUTPUT_LENGTH:
            stdout_text = stdout_text[:MAX_OUTPUT_LENGTH] + f"\n... (truncated, {len(stdout_text) - MAX_OUTPUT_LENGTH} more characters)"
        
        if len(stderr_text) > MAX_OUTPUT_LENGTH:
            stderr_text = stderr_text[:MAX_OUTPUT_LENGTH] + f"\n... (truncated, {len(stderr_text) - MAX_OUTPUT_LENGTH} more characters)"
        
        return {
            "stdout": stdout_text,
            "stderr": stderr_text,
            "exit_code": process.returncode,
            "working_dir": cwd
        }
        
    except Exception as e:
        return {
            "stdout": "",
            "stderr": str(e),
            "exit_code": -1,
            "working_dir": working_dir or "unknown",
            "error": "exception"
        }

# Create server instance
server = Server("terminal-server")

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available terminal tools."""
    return [
        Tool(
            name="execute_command",
            description=f"Execute a shell command in one of the allowed directories. Allowed directories: {', '.join(ALLOWED_DIRS)}. Supports ansible, terraform, packer, and other CLI tools.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The command to execute (e.g., 'ansible-playbook site.yml', 'terraform plan', 'packer build template.json')"
                    },
                    "working_directory": {
                        "type": "string",
                        "description": f"Working directory for command execution. Must be one of the allowed directories. If not specified, defaults to {ALLOWED_DIRS[0] if ALLOWED_DIRS else 'none configured'}"
                    },
                    "environment": {
                        "type": "object",
                        "description": "Additional environment variables to set for the command (optional)",
                        "additionalProperties": {
                            "type": "string"
                        }
                    }
                },
                "required": ["command"]
            }
        ),
        Tool(
            name="list_directory",
            description="List contents of a directory within allowed directories",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list"
                    },
                    "show_hidden": {
                        "type": "boolean",
                        "description": "Whether to show hidden files (default: false)"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="read_file",
            description="Read contents of a file within allowed directories",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path to read"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="get_working_directory",
            description="Get the current working directory and list of allowed directories",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict | None
) -> list[TextContent | ImageContent | EmbeddedResource]:
    """Handle tool execution requests."""
    
    if name == "execute_command":
        if not arguments or "command" not in arguments:
            raise ValueError("Missing required argument: command")
        
        command = arguments["command"]
        working_dir = arguments.get("working_directory")
        env = arguments.get("environment")
        
        result = await run_command(command, working_dir, shell=True, env=env)
        
        # Format response
        response = f"Command: {command}\n"
        response += f"Working Directory: {result['working_dir']}\n"
        response += f"Exit Code: {result['exit_code']}\n\n"
        
        if result['stdout']:
            response += f"STDOUT:\n{result['stdout']}\n\n"
        
        if result['stderr']:
            response += f"STDERR:\n{result['stderr']}\n"
        
        return [TextContent(type="text", text=response)]
    
    elif name == "list_directory":
        if not arguments or "path" not in arguments:
            raise ValueError("Missing required argument: path")
        
        path = arguments["path"]
        show_hidden = arguments.get("show_hidden", False)
        
        if not is_path_allowed(path):
            raise ValueError(f"Directory not allowed: {path}")
        
        try:
            dir_path = Path(path).resolve()
            entries = []
            
            for item in sorted(dir_path.iterdir()):
                if not show_hidden and item.name.startswith('.'):
                    continue
                
                entry_type = "dir" if item.is_dir() else "file"
                size = item.stat().st_size if item.is_file() else 0
                entries.append(f"[{entry_type}] {item.name} ({size} bytes)" if entry_type == "file" else f"[{entry_type}] {item.name}")
            
            response = f"Directory: {dir_path}\n\n"
            response += "\n".join(entries) if entries else "(empty directory)"
            
            return [TextContent(type="text", text=response)]
        
        except Exception as e:
            raise ValueError(f"Error listing directory: {str(e)}")
    
    elif name == "read_file":
        if not arguments or "path" not in arguments:
            raise ValueError("Missing required argument: path")
        
        path = arguments["path"]
        
        if not is_path_allowed(path):
            raise ValueError(f"File not allowed: {path}")
        
        try:
            file_path = Path(path).resolve()
            
            if not file_path.is_file():
                raise ValueError(f"Not a file: {path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if len(content) > MAX_OUTPUT_LENGTH:
                content = content[:MAX_OUTPUT_LENGTH] + f"\n... (truncated, {len(content) - MAX_OUTPUT_LENGTH} more characters)"
            
            response = f"File: {file_path}\n\n{content}"
            
            return [TextContent(type="text", text=response)]
        
        except UnicodeDecodeError:
            raise ValueError("File is not a text file or uses unsupported encoding")
        except Exception as e:
            raise ValueError(f"Error reading file: {str(e)}")
    
    elif name == "get_working_directory":
        response = f"Allowed Directories:\n"
        for i, dir_path in enumerate(ALLOWED_DIRS, 1):
            response += f"  {i}. {dir_path}\n"
        
        response += f"\nDefault Shell: {DEFAULT_SHELL}\n"
        response += f"Command Timeout: {TIMEOUT} seconds\n"
        
        return [TextContent(type="text", text=response)]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Run the terminal MCP server."""
    # Validate configuration
    if not ALLOWED_DIRS:
        print("WARNING: No allowed directories configured in terminal.config", file=sys.stderr)
        print("Server will not be able to execute commands", file=sys.stderr)
    
    # Log configuration
    print(f"Terminal MCP Server starting...", file=sys.stderr)
    print(f"Allowed directories: {ALLOWED_DIRS}", file=sys.stderr)
    print(f"Default shell: {DEFAULT_SHELL}", file=sys.stderr)
    
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="terminal",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())
