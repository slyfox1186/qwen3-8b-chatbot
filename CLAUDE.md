# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build/Test Commands

### Frontend (React/TypeScript)
- Development server: `cd frontend && npm run dev`
- Production build: `cd frontend && npm run build`
- Development build: `cd frontend && npm run build:dev`
- Lint: `cd frontend && npm run lint`
- Type check: `cd frontend && npm run typecheck`
- Preview build: `cd frontend && npm run preview`

### Backend (Python/FastAPI)
- Development server: `cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
- Quick start: `./start.sh` (runs both frontend and backend, handles Redis)
- Backend only: `./run-backend.sh`
- Frontend only: `./run-frontend.sh`
- Install dependencies: `cd backend && pip install -r requirements.txt`

### GPU Configuration
Before first run, configure GPU support in run-backend.sh. IMPORTANT: Uncomment ONE of these lines based on your GPU:
- NVIDIA: `export CMAKE_ARGS="-DLLAMA_CUBLAS=on"`
- AMD: `export CMAKE_ARGS="-DLLAMA_HIPBLAS=on"`
- Apple Silicon: `export CMAKE_ARGS="-DLLAMA_METAL=on"`

### Redis Stack Setup
The backend requires Redis Stack for memory and vector search:
```bash
# Using Docker (recommended)
docker run -d --name redis-stack -p 6379:6379 redis/redis-stack:latest

# Or install locally
# Ubuntu/Debian
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
sudo apt-get update
sudo apt-get install redis-stack-server
```

## Architecture Overview

### Backend Stack
- **FastAPI** web framework with async support
- **llama-cpp-python** for model inference (Qwen3-8B-Q8_0.gguf)
- **Redis Stack** for optimized conversation memory and vector search
  - Memory-optimized storage with Redis Hashes
  - Vector similarity search with RediSearch
  - 24-hour TTL with LRU eviction policy
- **SentenceTransformers** for semantic embeddings
- **DuckDuckGo Search** for privacy-focused web search
- **BeautifulSoup4** for HTML parsing and content extraction
- **Server-Sent Events (SSE)** for real-time token streaming

### Frontend Stack
- **React 18** with TypeScript (strict type checking)
- **Vite** for development and building
- **EventSource API** for SSE streaming
- **Markdown support** with react-markdown, remark-gfm, rehype plugins
- **Material-UI** for component styling

### Key Components

#### Backend Structure
```
backend/
├── main.py           # FastAPI app with chat and vector search endpoints
├── model.py          # Llama model initialization and streaming logic
├── memory.py         # Optimized Redis-based conversation storage
├── vector_search.py  # Vector similarity search for semantic lookups
├── utils.py          # Prompt formatting utilities
├── web_access.py     # Web search and content extraction
└── route_classifier.py # Classify queries for WEB/GENERAL routes
```

#### Frontend Structure
```
frontend/
├── src/
│   ├── App.tsx              # Main chat application logic
│   ├── api/
│   │   └── api.ts           # API client with SSE streaming
│   ├── components/
│   │   ├── ChatInput.tsx    # User input handling
│   │   ├── ChatMessage.tsx  # Message rendering with markdown
│   │   └── MarkdownRenderer.tsx  # Markdown rendering component
│   ├── styles/
│   │   ├── App.css          # Main application styles
│   │   ├── highlight.css    # Code highlighting styles
│   │   ├── markdown-it.css  # Markdown styles
│   │   └── markdown-renderer.css # Markdown renderer styles
│   ├── types/
│   │   └── types.ts         # TypeScript interfaces
│   └── utils/
│       └── markdown.ts       # Markdown utility functions
└── vite.config.ts          # Vite config with "/api" proxy
```

### API Endpoints
- `GET /health`: Health check and model information
- `GET/POST /chat_stream`: Stream chat responses via Server-Sent Events (SSE)
  - Query params for GET: `conv_id` (optional), `message` (required)
  - JSON body for POST: `{"conv_id": "...", "message": "..."}`
- `POST /conversation`: Create new conversation ID
- `GET /conversations`: List all conversations
- `DELETE /conversation/{conv_id}`: Clear specific conversation history
- `GET /memory_stats`: Get Redis memory usage statistics
- `POST /search`: Semantic vector search across conversations
  - Body: `{"query": "...", "limit": 5, "conv_id": "..."}`
- `POST /context`: Get relevant context from past conversations for RAG
  - Body: `{"query": "...", "limit": 5}`
- `POST /classify_route`: Determine if query needs WEB search or GENERAL response
  - Body: `{"query": "..."}`
- `POST /test_web_search`: Test web search functionality directly
  - Body: `{"query": "..."}`

### Code Conventions

#### TypeScript Frontend
- Path alias: `@/*` maps to `./src/*`
- Component names match filenames in PascalCase
- Interfaces for all component props and API responses
- Async operations wrapped in try/catch blocks
- EventSource for SSE streaming with proper error handling

#### Python Backend
- Type hints for all functions (Python 3.8+)
- Async/await pattern for all endpoints
- Pydantic models for request/response validation
- Generator pattern for streaming responses
- Environment variables for configuration

### Model Configuration
- Default model: `Qwen3-8B-Q8_0.gguf` (8-bit quantized)
- Context window: 8192 tokens
- GPU layers: -1 (full offload)
- Batch size: 512
- Model warm-up on startup to preload weights

### Development Workflow
1. Start Redis server (required for conversation memory)
2. Set GPU environment variables in run-backend.sh
3. Use `./start.sh` for concurrent frontend/backend development
4. Frontend proxies API calls to backend (configured in vite.config.ts)
5. Hot-reload enabled for both frontend and backend

### Error Handling
- Frontend displays user-friendly error messages
- Backend returns proper HTTP status codes
- SSE streams include error events for connection issues
- Redis connection failures handled gracefully
- Model loading errors caught during initialization

### Performance Optimizations

#### Model Performance
- Model weights preloaded on startup
- GPU acceleration with full layer offload
- Memory-mapped model loading (use_mmap=True)
- Token streaming for real-time responses

#### Redis Memory Optimizations
- Compact data structures using Redis hashes instead of JSON strings
- Pipelined Redis operations for reduced latency
- Server-side memory limit configuration with `maxmemory` setting
- LRU eviction policy with `volatile-lru` for TTL keys
- Optimized hash encoding with configurable settings
- Lazy freeing for non-blocking memory reclamation
- Redis connection pooling with automatic retry
- Memory usage monitoring via API endpoint

#### Vector Search Capabilities
- Semantic similarity search using embedding vectors
- Automatic indexing of messages with SentenceTransformers
- HNSW algorithm for approximate nearest neighbor search
- Contextual retrieval from past conversations
- Cross-conversation search capability
- Configurable similarity threshold

#### Web Search Integration
- Automatic route classification using AI to determine if web search is needed
- DuckDuckGo search integration for privacy-focused web search
- Intelligent content extraction from web pages
- Caching system for web content to reduce API calls
- Citation formatting for transparency
- Parallel fetching of search result contents
- Automatic handling of current events, news, and time-sensitive queries

### Testing and Development Patterns

#### Testing API Endpoints
```bash
# Test health endpoint
curl http://localhost:8000/health

# Test streaming chat
curl -N "http://localhost:8000/chat_stream?message=Hello"

# Test route classification
curl -X POST "http://localhost:8000/classify_route" \
  -H "Content-Type: application/json" \
  -d '{"query": "What is the weather today?"}'

# Test web search
curl -X POST "http://localhost:8000/test_web_search" \
  -H "Content-Type: application/json" \
  -d '{"query": "latest news"}'
```

#### Development Tips
- Use the `--reload` flag with uvicorn for hot-reloading during backend development
- Frontend proxies API requests via Vite config - no CORS setup needed in development
- Redis must be running before starting the backend
- Model warm-up happens on first request - initial response will be slower
- Use Chrome DevTools Network tab to debug SSE streaming issues
- Check Redis memory usage regularly via `/memory_stats` endpoint

#### Common Issues and Solutions
- **GPU not detected**: Ensure correct CMAKE_ARGS are set when installing llama-cpp-python
- **Redis connection failed**: Check Redis is running (`redis-cli ping`)
- **Model loading OOM**: Use a smaller quantized model or reduce context window
- **SSE not streaming**: Check for proxy issues or CORS configuration
- **High memory usage**: Configure Redis `maxmemory` and eviction policy

### Environment Configuration

Create a `.env` file in the backend directory based on `.env.example`:

```env
# Model Configuration
MODEL_PATH=../models/Qwen3-8B-Q8_0.gguf  # Path to GGUF model file
MODEL_CTX_SIZE=2048                      # Context window size
MODEL_GPU_LAYERS=-1                      # Number of layers to offload to GPU (-1 for all)
MODEL_THREADS=8                          # Number of CPU threads
MODEL_BATCH_SIZE=32                      # Batch size for prompt processing
MAX_TOKENS=512                           # Maximum tokens per response

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=                          # Leave empty for no password
REDIS_TTL=86400                         # TTL for conversation data (24 hours)

# API Configuration
DEFAULT_SYSTEM_PROMPT="You are a helpful assistant."
CORS_ORIGINS=http://localhost:3000       # Comma-separated list for multiple origins
```

For production deployment, ensure all sensitive values are properly configured in environment variables.

### Deployment Considerations

#### Production Setup
1. Use a proper process manager (systemd, supervisor, or Docker)
2. Configure Redis persistence for data durability
3. Set up a reverse proxy (nginx/Apache) with SSL
4. Implement rate limiting and request validation
5. Monitor GPU memory and temperature
6. Set up log rotation and monitoring
7. Configure automatic restarts on failure

#### Docker Deployment
```dockerfile
# Dockerfile example structure
FROM python:3.10-slim
# Install system dependencies for GPU support
# Copy requirements and install
# Copy model files
# Set environment variables
# Run with proper GPU access
```

#### Performance Tuning
- Adjust `MODEL_BATCH_SIZE` based on GPU memory
- Configure Redis maxmemory policy
- Use model quantization (Q4_0, Q5_1) for memory constraints
- Consider running multiple backend instances for high traffic
- Implement request queuing for concurrent users

#### Security Best Practices
- Use environment variables for sensitive configuration
- Implement API authentication (Bearer tokens, API keys)
- Validate and sanitize all user inputs
- Set up CORS properly for production domains
- Use HTTPS for all API communications
- Implement rate limiting per IP/user
- Monitor for prompt injection attempts