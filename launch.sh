#!/bin/bash
# Quick launcher for ITR Family Workspace Streamlit app

set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Ensure we're in the correct directory
cd "$SCRIPT_DIR"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Virtual environment not found!"
    echo "Please run: python3 setup.py"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env configuration not found!"
    echo "Please run: python3 setup.py"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

echo "🚀 Starting ITR Family Workspace..."
echo "📍 http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Launch Streamlit
streamlit run app.py --logger.level=info
