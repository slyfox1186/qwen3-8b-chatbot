#!/bin/bash

# Color definitions
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[0;37m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Check for --build argument
BUILD_MODE=false
if [[ "$1" == "--build" ]]; then
    BUILD_MODE=true
    echo -e "${GREEN}${BOLD}Running in production build mode...${NC}"
else
    echo -e "${BLUE}${BOLD}Running in development mode...${NC}"
fi

# Kill any running processes
echo -e "${YELLOW}Cleaning up existing processes...${NC}"
pkill -f "uvicorn main:app"
pkill -f "npm run dev"
pkill -f "npm run preview"

# Forcefully kill any process using port 8000 (backend) and 3000/4173 (frontend)
if command -v fuser > /dev/null; then
    echo -e "${YELLOW}Attempting to free ports 8000, 3000, 4173...${NC}"
    fuser -k 8000/tcp > /dev/null 2>&1
    fuser -k 3000/tcp > /dev/null 2>&1 # Default Vite dev port
    fuser -k 4173/tcp > /dev/null 2>&1 # Default Vite preview port
else
    echo -e "${YELLOW}fuser command not found. Skipping forceful port clearing.${NC}"
fi

# Check if Redis is running
if command -v redis-cli > /dev/null && ! redis-cli ping > /dev/null 2>&1; then
  echo -e "${YELLOW}Redis does not appear to be running. Starting Redis...${NC}"
  if command -v redis-server > /dev/null; then
    redis-server &
    REDIS_PID=$!
    echo -e "${GREEN}Redis started with PID $REDIS_PID${NC}"
  else
    echo -e "${RED}WARNING: Redis is not installed. Please install Redis or the conversation history won't work.${NC}"
  fi
fi

# Start the backend server
echo -e "${CYAN}${BOLD}Starting backend server...${NC}"

# Create backend logs directory if it doesn't exist
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_LOGS_DIR="$SCRIPT_DIR/backend/logs"
mkdir -p "$BACKEND_LOGS_DIR"

# Start the backend in a separate process with logging
BACKEND_LOG="$BACKEND_LOGS_DIR/backend.log"
echo -e "${CYAN}Backend server logs will be written to: $BACKEND_LOG${NC}"

# Create log files
> "$BACKEND_LOG"

# Function to colorize backend logs
colorize_backend() {
    while IFS= read -r line; do
        case "$line" in
            *ERROR*|*Error*|*error*)
                echo -e "${RED}[BACKEND] $line${NC}"
                ;;
            *WARNING*|*Warning*|*warning*)
                echo -e "${YELLOW}[BACKEND] $line${NC}"
                ;;
            *INFO*|*Info*|*info*)
                echo -e "${CYAN}[BACKEND] $line${NC}"
                ;;
            *SUCCESS*|*Success*|*success*)
                echo -e "${GREEN}[BACKEND] $line${NC}"
                ;;
            *)
                echo -e "${WHITE}[BACKEND] $line${NC}"
                ;;
        esac
    done
}

# Start backend server in background with colored output
if [ "$BUILD_MODE" = true ]; then
    # Production mode - no reload
    (cd "$(dirname "$0")/backend" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info 2>&1 | tee "$BACKEND_LOG" | colorize_backend) &
else
    # Development mode - with reload
    (cd "$(dirname "$0")/backend" && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level info 2>&1 | tee "$BACKEND_LOG" | colorize_backend) &
fi
BACKEND_PID=$!
echo -e "${GREEN}Backend server started with PID $BACKEND_PID${NC}"

# Wait for backend to start
echo -e "${YELLOW}Waiting for backend to start...${NC}"
sleep 5

# Create frontend logs directory if it doesn't exist
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_LOGS_DIR="$SCRIPT_DIR/frontend/logs"
mkdir -p "$FRONTEND_LOGS_DIR"

# Start frontend with logging
FRONTEND_LOG="$FRONTEND_LOGS_DIR/frontend.log"
echo -e "${PURPLE}Frontend server logs will be written to: $FRONTEND_LOG${NC}"

# Create log files
> "$FRONTEND_LOG"

# Function to colorize frontend logs
colorize_frontend() {
    while IFS= read -r line; do
        case "$line" in
            *ERROR*|*Error*|*error*)
                echo -e "${RED}[FRONTEND] $line${NC}"
                ;;
            *WARNING*|*Warning*|*warning*)
                echo -e "${YELLOW}[FRONTEND] $line${NC}"
                ;;
            *ready*|*Ready*|*started*|*Started*)
                echo -e "${GREEN}[FRONTEND] $line${NC}"
                ;;
            *VITE*|*vite*)
                echo -e "${PURPLE}[FRONTEND] $line${NC}"
                ;;
            *)
                echo -e "${WHITE}[FRONTEND] $line${NC}"
                ;;
        esac
    done
}

# Start frontend server in background with colored output
if [ "$BUILD_MODE" = true ]; then
    # Build for production
    echo -e "${PURPLE}Building frontend for production...${NC}"
    (cd "$SCRIPT_DIR/frontend" && npm run build)
    echo -e "${PURPLE}Starting production preview server...${NC}"
    (cd "$SCRIPT_DIR/frontend" && npm run preview 2>&1 | tee "$FRONTEND_LOG" | colorize_frontend) &
    FRONTEND_PID=$!
    FRONTEND_PORT=4173  # Vite preview default port
else
    # Development mode
    (cd "$SCRIPT_DIR/frontend" && npm run dev 2>&1 | tee "$FRONTEND_LOG" | colorize_frontend) &
    FRONTEND_PID=$!
    FRONTEND_PORT=3000  # Vite dev default port
fi
echo -e "${GREEN}Frontend server started with PID $FRONTEND_PID${NC}"

echo ""
echo -e "${GREEN}${BOLD}=========================================="
echo "Both servers are now running!"
echo -e "- Frontend: ${BLUE}http://localhost:$FRONTEND_PORT${GREEN}"
echo -e "- Backend API: ${BLUE}http://localhost:8000${GREEN}"
echo "- Press Ctrl+C to stop both servers"
if [ "$BUILD_MODE" = true ]; then
    echo -e "- Running in ${BOLD}PRODUCTION${GREEN} mode"
else
    echo -e "- Running in ${BOLD}DEVELOPMENT${GREEN} mode (with hot reload)"
fi
echo -e "==========================================${NC}"
echo ""
echo -e "${YELLOW}Log files:"
echo -e "- Backend: $BACKEND_LOG"
echo -e "- Frontend: $FRONTEND_LOG${NC}"
echo ""
echo -e "${CYAN}${BOLD}Showing live logs (both terminal and files):${NC}"
echo -e "${CYAN}==========================================${NC}"

# Function to handle exit
function cleanup {
  echo ""
  echo -e "${YELLOW}Stopping servers...${NC}"
  kill $FRONTEND_PID 2>/dev/null
  kill $BACKEND_PID 2>/dev/null
  if [ -n "$REDIS_PID" ]; then
    kill $REDIS_PID 2>/dev/null
  fi
  echo -e "${GREEN}Cleanup complete.${NC}"
  exit 0
}

# Register the cleanup function for SIGINT (Ctrl+C)
trap cleanup SIGINT

# Keep the script running and show combined logs
# This will show logs from both servers in the terminal
# The individual tee commands above ensure logs are also saved to files
wait