#!/bin/bash
# Web-Search MCP Server Setup Script
# Sets up Poetry environment for the web-search MCP server

set -e

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "Error: Poetry is not installed. Please install it first."
    exit 1
fi

echo "Setting up web-search MCP server environment..."

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

echo "✓ web-search MCP server environment ready"

