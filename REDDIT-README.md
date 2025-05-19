# Qwen3-8B Chatbot: A Full-Stack AI Chat Application with Token Streaming

![Qwen3-8B Chatbot Demo](https://i.imgur.com/placeholder.png)

## What is this?

This is a full-stack chatbot application that runs the Qwen3-8B language model locally on your machine. It features:

- **GPU-accelerated inference** with llama-cpp-python
- **Token-by-token streaming** for a ChatGPT-like experience
- **"Thinking" mode** that shows the model's reasoning process
- **Redis-backed memory** for conversation history
- **Web search capability** for up-to-date information
- **React/TypeScript frontend** with a clean, responsive UI

## Why I Built This

After struggling for days to get token streaming working correctly, I finally cracked the code on how to properly implement a full-stack AI application with real-time token streaming. The standard EventSource approach has some limitations, so I developed a custom fetch-based SSE client that provides much better control and reliability.

I'm sharing this project so others can learn from my experience and build their own AI applications without going through the same pain points.

## How to Set It Up Using an AI Assistant

One of the coolest things about this project is that you can set it up with the help of an AI assistant like Claude, GPT-4, or any other capable LLM. Here's how:

### 1. Clone the Repository

First, clone the repository to your local machine:

```bash
git clone https://github.com/slyfox1186/qwen3-8b-chatbot.git
cd qwen3-8b-chatbot
```

### 2. Use an AI Assistant to Set Up the Project

1. Open your favorite AI assistant (Claude, GPT-4, etc.)
2. Share these files with the assistant (they contain detailed technical documentation):
   - `README.md` - Main project documentation
   - `flow_diagram.md` - High-level flow diagram of the application
   - `FRONTEND_FLOW_ANALYSIS.md` - Detailed analysis of the frontend code
   - `BACKEND_FLOW_ANALYSIS.md` - Detailed analysis of the backend code

3. Ask the assistant to help you set up the project with a prompt like:

```
I'm setting up the qwen3-8b-chatbot project. I've cloned the repository and I'm looking at the documentation. Can you help me get it running on my system? I have [describe your system: OS, GPU, etc.].
```

The documentation is comprehensive enough that the assistant should be able to guide you through the entire setup process in a single conversation, including:

- Installing dependencies
- Setting up Redis
- Downloading the model files
- Configuring the application
- Running the frontend and backend

### 3. Install Redis Stack Server

This project uses Redis Stack Server for conversation memory and vector search capabilities. Here's how to set it up:

#### For Linux:

```bash
# Add the Redis repository
curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list

# Update and install Redis Stack Server
sudo apt-get update
sudo apt-get install redis-stack-server

# Start Redis Stack Server
sudo systemctl start redis-stack-server
```

#### For macOS (using Homebrew):

```bash
# Install Redis Stack
brew tap redis-stack/redis-stack
brew install redis-stack

# Start Redis Stack Server
brew services start redis-stack
```

#### For Windows:

1. Download the Redis Stack Server installer from [Redis Stack Downloads](https://redis.io/download/)
2. Run the installer and follow the prompts
3. Make sure the service is running after installation

#### Using Docker:

```bash
docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
```

### 4. Download the Model File

You'll need to download the Qwen3-8B model file in GGUF format. The assistant can provide you with the latest download links, but here are some options:

- [Qwen3-8B-Q8_0.gguf](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q8_0.gguf) (8-bit quantized, ~4.5GB)
- [Qwen3-8B-Q6_K_L.gguf](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q6_K_L.gguf) (6-bit quantized, ~3.5GB)
- [Qwen3-8B-Q4_K_M.gguf](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf) (4-bit quantized, ~2.5GB)

Place the downloaded model file in the `backend/models` directory.

### 5. Review and Customize Configuration (`config.py`) (Optional)

This project uses a centralized configuration file, `backend/config.py`, to manage important settings. While the application comes with sensible defaults, you might want to customize it based on your setup or preferences.

**Location:** `qwen3-8b-chatbot/backend/config.py`

**Key Settings You Can Modify:**

*   **Model Path:** `MODEL_PATH` (e.g., if you've downloaded a different GGUF quantization or renamed the file).
*   **LLM Parameters:** `MAX_TOKENS_GENERATION`, `TEMPERATURE`, `N_CTX`, `N_GPU_LAYERS`, etc., to fine-tune the model's behavior and performance.
*   **Redis Connection:** `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` if your Redis server is not running on the default `localhost:6379` or requires a password.
*   **Embedding Model:** `EMBEDDING_MODEL_NAME` for vector search.
*   **System Prompts:** `DEFAULT_SYSTEM_PROMPT`, `CLASSIFIER_SYSTEM_PROMPT`, `QUERY_OPTIMIZER_SYSTEM_PROMPT` to change the chatbot's core behavior or classification logic.

**How to Configure:**

The `config.py` script loads settings from environment variables first, then falls back to default values defined directly in the file. You can:

1.  **Edit `backend/config.py` directly:** For persistent changes, modify the default values in the script.
2.  **Set Environment Variables:** For temporary overrides or for containerized deployments, set the corresponding environment variables (e.g., `export MODEL_PATH="./models/your_model.gguf"`).

Most users can start with the default settings. Review this file if you encounter issues related to model loading, Redis connection, or if you wish to experiment with different model parameters.

## Technical Details

This project demonstrates several advanced techniques:

1. **Custom SSE Client**: A fetch-based Server-Sent Events client that provides better control and reliability than the native EventSource API.

2. **Token Streaming**: Real-time streaming of tokens from the model to the frontend, with proper handling of thinking tags.

3. **Thinking Mode**: The ability to see the model's reasoning process in real-time before it provides the final answer.

4. **Vector Search**: Redis Stack-backed vector similarity search for retrieving relevant past conversations using the RediSearch module and BGE embeddings.

5. **Web Search Integration**: Automatic detection of queries that need web search and integration of search results into the model's context.

6. **Redis Memory System**: Efficient conversation storage and retrieval using Redis data structures with optimized memory usage and TTL-based expiration.

## Requirements

- Python 3.8+
- Node.js 16+
- Redis Stack Server (for memory and vector search capabilities)
- A GPU with 8GB+ VRAM (for best performance)

## Project Structure

```
qwen3-8b-chatbot/
├── backend/               # Python FastAPI backend
│   ├── models/            # Directory for model files
│   ├── config.py          # Centralized application configuration
│   ├── main.py            # Main FastAPI application
│   ├── model.py           # Model inference code
│   ├── memory.py          # Redis-based memory management
│   ├── route_classifier.py # Query classification
│   ├── web_access.py      # Web search functionality
│   └── requirements.txt   # Python dependencies
├── frontend/              # React/TypeScript frontend
│   ├── src/               # Source code
│   │   ├── api/           # API integration
│   │   ├── components/    # React components
│   │   ├── styles/        # CSS styles
│   │   └── types/         # TypeScript type definitions
│   ├── package.json       # Node.js dependencies
│   └── tsconfig.json      # TypeScript configuration
├── README.md              # Main documentation
├── flow_diagram.md        # Flow diagram of the application
├── FRONTEND_FLOW_ANALYSIS.md # Detailed frontend analysis
└── BACKEND_FLOW_ANALYSIS.md  # Detailed backend analysis
```

## Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

## License

This project is open source under the MIT License. See the LICENSE file for details.

Note that the Qwen3 model itself may have its own license terms, so please check those before using it in your own projects.

---

If you find this project helpful, please give it a star on GitHub and share it with others who might be interested!

Created by [slyfox1186](https://github.com/slyfox1186)
