#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "📦 Installing frontend dependencies..."
npm install --silent

echo "🚀 Starting frontend on http://localhost:5173"
npm run dev
