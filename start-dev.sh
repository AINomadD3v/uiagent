#!/usr/bin/env bash

# UIAutodev Development Server Starter
# Starts both frontend and backend servers in parallel

set -e

echo "🚀 Starting UIAutodev Development Servers..."
echo "================================================"

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Shutting down servers..."
    jobs -p | xargs -r kill
    exit 0
}

# Trap Ctrl+C to cleanup
trap cleanup SIGINT SIGTERM

# Start backend server
echo "🔧 Starting backend server (port 20242)..."
nix develop --command uvicorn app:app --host 127.0.0.1 --port 20242 --reload &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 2

# Start frontend server
echo "🎨 Starting frontend server (port 5173)..."
cd frontend
nix develop --command npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for servers to initialize
sleep 3

echo ""
echo "✅ Development servers started!"
echo "================================================"
echo "📡 Backend API: http://127.0.0.1:20242"
echo "🌐 Frontend:    http://localhost:5173"
echo "📖 API Docs:    http://127.0.0.1:20242/docs"
echo "================================================"
echo "Press Ctrl+C to stop all servers"
echo ""

# Wait for background processes
wait $BACKEND_PID $FRONTEND_PID