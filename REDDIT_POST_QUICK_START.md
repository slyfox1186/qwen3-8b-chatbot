# Launch Your Own Qwen3-8B Chatbot! (Local, Streaming, Easy Setup)

Hey r/[relevant_subreddit],

I've put together a **Qwen3-8B Full-Stack Chatbot** project. This allows you to run a local AI with features such as:

*   **ChatGPT-like Token Streaming**
*   Real-time "Thinking Mode"
*   Conversation Memory (Redis-powered)
*   Web Search for up-to-date answers
*   Clean React/TypeScript UI

**Get the Code:** [`https://github.com/slyfox1186/qwen3-8b-chatbot`](https://github.com/slyfox1186/qwen3-8b-chatbot)

## Quick Start Guide (Fastest Way to Run)

Once you've cloned the repo (`git clone https://github.com/slyfox1186/qwen3-8b-chatbot.git` and `cd qwen3-8b-chatbot`), here are the essentials:

**1. Install Redis Stack Server:**
   Needed for memory & vector search. Pick your OS:

   *   **Linux (Debian/Ubuntu):**
       ```bash
       curl -fsSL https://packages.redis.io/gpg | sudo gpg --dearmor -o /usr/share/keyrings/redis-archive-keyring.gpg
       echo "deb [signed-by=/usr/share/keyrings/redis-archive-keyring.gpg] https://packages.redis.io/deb $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/redis.list
       sudo apt-get update && sudo apt-get install redis-stack-server && sudo systemctl start redis-stack-server
       ```
   *   **macOS (Homebrew):**
       ```bash
       brew tap redis-stack/redis-stack && brew install redis-stack && brew services start redis-stack
       ```
   *   **Docker (Easiest for many!):**
       ```bash
       docker run -d --name redis-stack -p 6379:6379 -p 8001:8001 redis/redis-stack:latest
       ```
       (Windows users: Docker or check full README for native install)

**2. Download the Qwen3-8B Model (GGUF):**
   A good default is the 8-bit quantized version (~4.5GB).
   *   **Download Link:** [`Qwen3-8B-Q8_0.gguf`](https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q8_0.gguf)
   *   **Important:** Save it as `qwen3-8b-chatbot/backend/models/Qwen3-8B-Q8_0.gguf`.
     (You might need to create the `backend/models` folder.)

**3. (Optional) Check Config:**
   *   Most settings are in `backend/config.py`. Defaults usually work!
   *   If your model path or Redis setup is non-standard, tweak it there or use environment variables.

**4. Run It!**
   The `start.sh` script handles everything else (dependencies, starting servers):
   ```bash
   ./start.sh
   ```
   This will launch the backend (default: `http://localhost:8000`) and frontend (default: `http://localhost:3000`, opens in browser).

---

That's it! You should be chatting with your local Qwen3-8B.
For more details, advanced setup, or troubleshooting, check the full `REDDIT-README.md` in the GitHub repo.

Happy chatting, and let me know what you think!
