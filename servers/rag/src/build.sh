#!/bin/bash
# RAG MCP Server PyInstaller Build Script (Linux) via Poetry

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENTRYPOINT="$SCRIPT_DIR/rag.py"
OUTPUT_DIR="$PROJECT_ROOT"
BUILD_DIR="$SCRIPT_DIR/.build"

echo "==> Building RAG MCP binary using Poetry"

if ! command -v poetry >/dev/null 2>&1; then
  echo "Error: poetry not found in PATH" >&2
  exit 1
fi

# Clean build artifacts
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# Ensure dependencies installed in Poetry context (no project install)
export POETRY_VIRTUALENVS_IN_PROJECT=true
export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
(cd "$SCRIPT_DIR" && poetry install --no-root >/dev/null)

echo "==> Running PyInstaller via Poetry"
(cd "$SCRIPT_DIR" && poetry run python -m pip install -q --upgrade pip && poetry run python -m pip install -q pyinstaller)
(cd "$SCRIPT_DIR" && poetry run pyinstaller \
  --onefile \
  --name rag.mcp \
  --distpath "$OUTPUT_DIR" \
  --workpath "$BUILD_DIR/pyi-build" \
  --specpath "$BUILD_DIR" \
  "$ENTRYPOINT")

# Optional: remove Poetry in-project venv after build to keep tree clean
if [ -d "$SCRIPT_DIR/.venv" ]; then
  rm -rf "$SCRIPT_DIR/.venv"
fi

# Remove poetry.lock if generated during install
if [ -f "$SCRIPT_DIR/poetry.lock" ]; then
  rm -f "$SCRIPT_DIR/poetry.lock"
fi

echo "==> Build complete: $OUTPUT_DIR/rag.mcp"

# Final cleanup of build artifacts
rm -rf "$BUILD_DIR"

