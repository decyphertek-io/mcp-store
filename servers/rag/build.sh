#!/bin/bash
# Build script for RAG MCP server
# Mirrors launch.sh logic exactly

set -e

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Setting up RAG MCP server environment..."

# Configure Poetry to create .venv in project directory (not global)
export POETRY_VIRTUALENVS_IN_PROJECT=true
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring

# Check if virtual environment exists
VENV_PATH=".venv"
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating new Poetry virtual environment in .venv"
    poetry install --no-root
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment exists"
fi

echo "✓ RAG MCP server environment ready"

