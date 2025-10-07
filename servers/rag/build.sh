#!/bin/bash
# RAG MCP Server Setup Script
# Sets up Poetry environment for the RAG MCP server

set -e

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Error: Poetry is not installed. Please install it first."
    exit 1
fi

echo "Setting up RAG MCP server environment..."

# Configure Poetry to create .venv in this directory
export POETRY_VIRTUALENVS_IN_PROJECT=true
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "Creating new Poetry virtual environment in .venv"
    poetry install --no-root
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
    # Ensure dependencies are up to date
    poetry install --no-root
fi

echo "✓ RAG MCP server environment ready"

