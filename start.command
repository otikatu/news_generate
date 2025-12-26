#!/bin/bash

# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 Starting Personalized Summary System..."

# Check if venv exists and activate it
if [ -d "venv" ]; then
    echo "📦 Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  'venv' directory not found."
    echo "   Attempting to run with system python..."
fi

# Run Streamlit app
# Check if streamlit is installed
if ! command -v streamlit &> /dev/null; then
    echo "❌ Streamlit could not be found."
    echo "   Please install dependencies: pip install -r requirements.txt"
    exit 1
fi

echo "✅ Launching Streamlit..."
streamlit run app.py
