#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "📦 Installing Python dependencies..."
pip install -r requirements.txt --quiet

echo "🚀 Starting backend on http://localhost:8000"
python main.py
