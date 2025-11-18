#!/bin/bash
#
# ICP Compute - Quick Start Script
# Starts all services in tmux sessions
#

set -e

echo "╔══════════════════════════════════════════════════════════╗"
echo "║         ICP COMPUTE - STARTING ALL SERVICES             ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# Check if tmux is installed
if ! command -v tmux &> /dev/null; then
    echo "❌ tmux not installed. Install with:"
    echo "   Mac: brew install tmux"
    echo "   Ubuntu: sudo apt install tmux"
    exit 1
fi

# Check if Redis is running
if ! redis-cli ping &> /dev/null; then
    echo "⚠️  Redis not running. Starting Redis..."
    redis-server --daemonize yes
    sleep 2
    if redis-cli ping &> /dev/null; then
        echo "✓ Redis started"
    else
        echo "❌ Failed to start Redis"
        exit 1
    fi
else
    echo "✓ Redis already running"
fi

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "   Copy .env.example to .env and fill in your API keys"
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "✓ Activating virtual environment..."
    source venv/bin/activate
else
    echo "⚠️  No virtual environment found"
    echo "   Create one with: python -m venv venv"
    echo "   Then run: source venv/bin/activate && pip install -r requirements.txt"
fi

# Kill existing ICPX tmux session if it exists
tmux kill-session -t icpx 2>/dev/null || true

echo ""
echo "🚀 Starting ICPX in tmux session..."
echo ""

# Create new tmux session with 3 panes
tmux new-session -d -s icpx -n services

# Split window into 3 panes
tmux split-window -h -t icpx:services
tmux split-window -v -t icpx:services

# Pane 0: API Server
tmux send-keys -t icpx:services.0 "source venv/bin/activate 2>/dev/null || true" C-m
tmux send-keys -t icpx:services.0 "echo '🌐 Starting API Server on http://localhost:8000'" C-m
tmux send-keys -t icpx:services.0 "uvicorn main:app --reload --port 8000" C-m

# Pane 1: Background Worker
tmux send-keys -t icpx:services.1 "source venv/bin/activate 2>/dev/null || true" C-m
tmux send-keys -t icpx:services.1 "echo '⚙️  Starting Background Worker'" C-m
tmux send-keys -t icpx:services.1 "sleep 3 && dramatiq main" C-m

# Pane 2: Logs/Control
tmux send-keys -t icpx:services.2 "source venv/bin/activate 2>/dev/null || true" C-m
tmux send-keys -t icpx:services.2 "echo '📊 ICPX Control Panel'" C-m
tmux send-keys -t icpx:services.2 "echo ''" C-m
tmux send-keys -t icpx:services.2 "echo 'Services running:'" C-m
tmux send-keys -t icpx:services.2 "echo '  • API Server: http://localhost:8000'" C-m
tmux send-keys -t icpx:services.2 "echo '  • API Docs: http://localhost:8000/docs'" C-m
tmux send-keys -t icpx:services.2 "echo '  • Worker: Running in background'" C-m
tmux send-keys -t icpx:services.2 "echo ''" C-m
tmux send-keys -t icpx:services.2 "echo 'Commands:'" C-m
tmux send-keys -t icpx:services.2 "echo '  • Test API: curl http://localhost:8000'" C-m
tmux send-keys -t icpx:services.2 "echo '  • Switch panes: Ctrl+B then arrow keys'" C-m
tmux send-keys -t icpx:services.2 "echo '  • Detach: Ctrl+B then D'" C-m
tmux send-keys -t icpx:services.2 "echo '  • Reattach: tmux attach -t icpx'" C-m
tmux send-keys -t icpx:services.2 "echo '  • Kill all: tmux kill-session -t icpx'" C-m
tmux send-keys -t icpx:services.2 "echo ''" C-m
tmux send-keys -t icpx:services.2 "echo '🎯 Ready to generate leads!'" C-m
tmux send-keys -t icpx:services.2 "echo ''" C-m

# Set pane layout
tmux select-layout -t icpx:services main-vertical

# Attach to session
echo "✓ All services started!"
echo ""
echo "Attaching to tmux session..."
echo ""
echo "To detach: Press Ctrl+B, then D"
echo "To reattach: tmux attach -t icpx"
echo "To kill all: tmux kill-session -t icpx"
echo ""

sleep 2
tmux attach -t icpx
