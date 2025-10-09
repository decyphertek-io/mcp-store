# Terminal MCP Server

A secure Model Context Protocol (MCP) server that provides terminal access to specified directories for running CLI tools like Ansible, Terraform, Packer, and other command-line utilities.

## Overview

The Terminal MCP Server allows AI assistants to execute shell commands within pre-configured, allowed directories. This provides a secure way to interact with infrastructure-as-code tools and other CLI utilities while maintaining control over which directories can be accessed.

## Features

- **Secure Directory Access**: Only allows command execution within pre-configured directories
- **Multiple Tool Support**: Run Ansible playbooks, Terraform plans, Packer builds, and more
- **Command Execution**: Execute shell commands with full output capture
- **Directory Listing**: Browse files and directories within allowed paths
- **File Reading**: Read file contents for inspection
- **Environment Variables**: Pass custom environment variables to commands
- **Configurable Timeouts**: Set maximum execution time for commands
- **Output Truncation**: Automatic truncation of large outputs to prevent memory issues

## Installation

### Prerequisites

- Python 3.10 or higher
- Poetry (for building)
- Linux operating system

### Building the Server

1. Navigate to the source directory:
```bash
cd /path/to/terminal/src
```

2. Run the build script:
```bash
./build.sh
```

This will create a standalone `terminal.mcp` binary in the parent directory.

## Configuration

### terminal.config

The server reads its configuration from `terminal.config` in the root directory. Here's an example:

```json
{
  "allowed_directories": [
    "/home/adminotaur/ansible",
    "/home/adminotaur/terraform",
    "/home/adminotaur/packer",
    "/home/adminotaur/Documents"
  ],
  "default_shell": "/bin/bash",
  "max_output_length": 10000,
  "command_timeout": 300
}
```

#### Configuration Options

- **allowed_directories** (required): List of absolute paths where commands can be executed
- **default_shell** (optional): Shell to use for command execution (default: `/bin/bash`)
- **max_output_length** (optional): Maximum number of characters in output before truncation (default: 10000)
- **command_timeout** (optional): Maximum execution time in seconds (default: 300)

### MCP Settings Configuration

Add the server to your MCP settings file (usually at `~/.config/Cursor/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`):

```json
{
  "mcpServers": {
    "terminal": {
      "command": "/path/to/terminal.mcp",
      "args": [],
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

## Available Tools

### 1. execute_command

Execute a shell command in an allowed directory.

**Parameters:**
- `command` (required): The shell command to execute
- `working_directory` (optional): Directory to execute the command in (must be in allowed directories)
- `environment` (optional): Additional environment variables as key-value pairs

**Example:**
```json
{
  "command": "ansible-playbook site.yml -i inventory.ini",
  "working_directory": "/home/adminotaur/ansible",
  "environment": {
    "ANSIBLE_HOST_KEY_CHECKING": "False"
  }
}
```

### 2. list_directory

List contents of a directory within allowed directories.

**Parameters:**
- `path` (required): Directory path to list
- `show_hidden` (optional): Whether to show hidden files (default: false)

**Example:**
```json
{
  "path": "/home/adminotaur/terraform",
  "show_hidden": true
}
```

### 3. read_file

Read contents of a file within allowed directories.

**Parameters:**
- `path` (required): File path to read

**Example:**
```json
{
  "path": "/home/adminotaur/ansible/playbook.yml"
}
```

### 4. get_working_directory

Get information about allowed directories and server configuration.

**Parameters:** None

**Returns:** List of allowed directories, default shell, and timeout settings.

## Usage Examples

### Running Ansible Playbooks

```bash
# List available playbooks
Tool: list_directory
{
  "path": "/home/adminotaur/ansible"
}

# Read a playbook
Tool: read_file
{
  "path": "/home/adminotaur/ansible/webserver.yml"
}

# Execute the playbook
Tool: execute_command
{
  "command": "ansible-playbook webserver.yml -i inventory.ini --check",
  "working_directory": "/home/adminotaur/ansible"
}
```

### Running Terraform

```bash
# Initialize Terraform
Tool: execute_command
{
  "command": "terraform init",
  "working_directory": "/home/adminotaur/terraform/aws-infrastructure"
}

# Plan changes
Tool: execute_command
{
  "command": "terraform plan",
  "working_directory": "/home/adminotaur/terraform/aws-infrastructure"
}

# Apply changes
Tool: execute_command
{
  "command": "terraform apply -auto-approve",
  "working_directory": "/home/adminotaur/terraform/aws-infrastructure"
}
```

### Running Packer

```bash
# Validate Packer template
Tool: execute_command
{
  "command": "packer validate template.json",
  "working_directory": "/home/adminotaur/packer"
}

# Build image
Tool: execute_command
{
  "command": "packer build template.json",
  "working_directory": "/home/adminotaur/packer",
  "environment": {
    "PKR_VAR_aws_region": "us-east-1"
  }
}
```

## Security Considerations

### Path Restrictions

The server enforces strict path validation:
- All operations must be within configured `allowed_directories`
- Symbolic links are resolved to absolute paths for validation
- Path traversal attempts are blocked

### Command Execution

- Commands run with the same permissions as the MCP server process
- No privilege escalation is performed
- Commands inherit the server's environment unless overridden

### Best Practices

1. **Limit Allowed Directories**: Only configure directories that need terminal access
2. **Use Specific Paths**: Prefer specific project directories over broad paths like `/home`
3. **Review Commands**: Use the `--check` or `--dry-run` flags when available
4. **Monitor Output**: Check command exit codes and stderr for errors
5. **Set Appropriate Timeouts**: Adjust `command_timeout` based on expected execution times

## Troubleshooting

### "Directory not allowed" Error

**Cause**: Attempting to access a directory not in `allowed_directories`

**Solution**: Add the directory to `terminal.config` and restart the server

### Command Timeout

**Cause**: Command execution exceeded `command_timeout` setting

**Solution**: Increase the timeout in `terminal.config` or optimize the command

### Permission Denied

**Cause**: MCP server doesn't have permission to access files/directories

**Solution**: Ensure the server process has appropriate file system permissions

### Output Truncated

**Cause**: Command output exceeded `max_output_length`

**Solution**: Increase the limit in `terminal.config` or redirect output to a file

## Development

### Project Structure

```
terminal/
├── src/
│   ├── terminal.py          # Main server implementation
│   ├── build.sh            # Build script
│   └── pyproject.toml      # Python dependencies
├── terminal.config         # Server configuration
├── terminal.json          # Server metadata
├── terminal.md            # This documentation
└── terminal.mcp           # Compiled binary (after build)
```

### Dependencies

- **mcp**: Model Context Protocol SDK
- **asyncio**: Asynchronous I/O for Python
- **pathlib**: Object-oriented filesystem paths

### Building from Source

```bash
cd src
./build.sh
```

The build script:
1. Creates a virtual environment using Poetry
2. Installs dependencies
3. Uses PyInstaller to create a standalone binary
4. Cleans up temporary files

## Version History

### 0.1.0 (Current)
- Initial release
- Basic command execution
- Directory listing and file reading
- Configurable allowed directories
- Command timeout support
- Output truncation

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions, please visit the project repository.
