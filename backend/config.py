import os
from dotenv import load_dotenv

# Load .env file if it exists, for local development convenience
load_dotenv()

# ============================================================================ #
#                    GENERAL APPLICATION SETTINGS                          #
# ============================================================================ #
APP_NAME = "Qwen3-8B Chatbot"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper() # For Python's logging module

# ============================================================================ #
#                  API SERVER SETTINGS (FastAPI/Uvicorn)                       #
# ============================================================================ #
# These are typically set when running Uvicorn, e.g., in start.sh
# However, they can be documented here for clarity or used if Uvicorn is run programmatically.
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
CORS_ORIGINS_STRING = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:4173")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_STRING.split(",")]

# ============================================================================ #
#                 LLM MODEL SETTINGS (llama-cpp-python)                      #
# ============================================================================ #
# Path to the GGUF model file
MODEL_PATH = os.getenv("MODEL_PATH", "./models/Qwen3-8B-Q8_0.gguf") # Make sure this path is relative to the backend directory or use absolute

# Core LLM generation parameters
MAX_TOKENS_GENERATION = int(os.getenv("MAX_TOKENS_GENERATION", "1024")) # Max tokens for a full response
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
TOP_K = int(os.getenv("TOP_K", "40"))
TOP_P = float(os.getenv("TOP_P", "0.95"))
MIN_P = float(os.getenv("MIN_P", "0.05")) # llama-cpp-python specific
REPEAT_PENALTY = float(os.getenv("REPEAT_PENALTY", "1.1")) # Default in llama-cpp

# LlamaCPP specific hardware/performance settings
N_CTX = int(os.getenv("N_CTX", "4096")) # Context window size
N_THREADS = int(os.getenv("N_THREADS", os.cpu_count() or 4)) # Number of CPU threads
N_BATCH = int(os.getenv("N_BATCH", "512")) # Batch size for prompt processing
N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "-1")) # -1 to offload all possible layers to GPU, 0 for CPU only
MAIN_GPU = int(os.getenv("MAIN_GPU", "0")) # Main GPU to use for offloading
# Advanced memory/performance options
USE_MLOCK = os.getenv("USE_MLOCK", "True").lower() == "true" # Use mlock to prevent swapping
USE_MMAP = os.getenv("USE_MMAP", "True").lower() == "true"   # Use mmap for faster model loading
OFFLOAD_KQV = os.getenv("OFFLOAD_KQV", "True").lower() == "true" # Offload KQV caches to GPU
FLASH_ATTN = os.getenv("FLASH_ATTN", "True").lower() == "true" # Enable Flash Attention (if supported by model and hardware)
LLAMA_VERBOSE = os.getenv("LLAMA_VERBOSE", "False").lower() == "true" # Verbose output from llama-cpp-python

# ============================================================================ #
#                         DEFAULT SYSTEM PROMPTS                             #
# ============================================================================ #
DEFAULT_SYSTEM_PROMPT = os.getenv(
    "DEFAULT_SYSTEM_PROMPT",
    "You are a helpful AI assistant. Provide clear, concise, and accurate responses. Current date: {current_date}"
)

# ============================================================================ #
#           REDIS SETTINGS (for Conversation Memory & Vector Search)         #
# ============================================================================ #
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None) # Default to None if not set
REDIS_DB = int(os.getenv("REDIS_DB", "0")) # Default Redis DB
REDIS_TTL_SECONDS = int(os.getenv("REDIS_TTL_SECONDS", "86400"))  # Default TTL for keys: 24 hours

# Redis memory management (if Redis Stack is not managing it automatically)
REDIS_MAX_MEMORY = os.getenv("REDIS_MAX_MEMORY", "256mb") # Max memory for Redis
REDIS_MAX_MEMORY_POLICY = os.getenv("REDIS_MAX_MEMORY_POLICY", "allkeys-lru") # Eviction policy

# ============================================================================ #
#              VECTOR SEARCH & EMBEDDING MODEL SETTINGS                      #
# ============================================================================ #
# SentenceTransformer model for embeddings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-base-en-v1.5") # Smaller, faster default
# For BAAI/bge-large-en-v1.5, dimension is 1024. For bge-base-en-v1.5, it's 768.
# It's better to get this dynamically from the model, but a config can be a fallback.
# VECTOR_DIMENSION = int(os.getenv("VECTOR_DIMENSION", "768")) # Set based on EMBEDDING_MODEL_NAME
VECTOR_SIMILARITY_THRESHOLD = float(os.getenv("VECTOR_SIMILARITY_THRESHOLD", "0.75")) # For retrieving similar messages
BGE_QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages:" # Instruction for BGE query embeddings
VECTOR_INDEX_NAME = "chatbot_message_vectors" # Name for the Redis Search index

# ============================================================================ #
#            ROUTE CLASSIFIER & QUERY OPTIMIZER SETTINGS                     #
# ============================================================================ #
# System prompt for the LLM when it's classifying user queries for web search
CLASSIFIER_SYSTEM_PROMPT = os.getenv("CLASSIFIER_SYSTEM_PROMPT", """
You are a route classifier that determines if queries need current information from the web.
Respond with ONLY "WEB" or "GENERAL". Today's date is {current_date}.
Use "WEB" for queries about: current events, news, weather, sports scores, recent dates,
frequently changing information, latest versions, prices, updates, time-sensitive information,
real-time data, info after your training cutoff, current political figures, officeholders,
leaders, stock values, or sports teams/players/standings.
Use "GENERAL" for: historical facts, established knowledge, concepts, definitions,
explanations, math, science, theories, general advice, opinions, creative writing,
information that doesn't change frequently, or simple greetings.
Ensure your response is ONLY "WEB" or "GENERAL". Do not include any other text or thinking tags. /no_think
""".strip())

# System prompt for the LLM when it's optimizing user queries for search engines
QUERY_OPTIMIZER_SYSTEM_PROMPT = os.getenv("QUERY_OPTIMIZER_SYSTEM_PROMPT", """
You are an expert at reformulating user questions into highly effective search engine queries.
Convert the given user question into a concise and keyword-focused query that a search engine
like Google or DuckDuckGo can understand well. Remove any conversational fluff.
Return ONLY the optimized search query. /no_think
""".strip())

CLASSIFIER_MAX_TOKENS = int(os.getenv("CLASSIFIER_MAX_TOKENS", "30")) # Max tokens for classification response
OPTIMIZER_MAX_TOKENS = int(os.getenv("OPTIMIZER_MAX_TOKENS", "50")) # Max tokens for optimized query

# ============================================================================ #
#                 FRONTEND SETTINGS (Informational)                          #
# ============================================================================ #
# These are not directly used by the backend Python code but are good to document.
FRONTEND_DEV_PORT = int(os.getenv("FRONTEND_DEV_PORT", "3000"))
FRONTEND_PREVIEW_PORT = int(os.getenv("FRONTEND_PREVIEW_PORT", "4173")) # Vite's default preview port

# ============================================================================ #
#           UTILITY FUNCTION TO PRINT CONFIGURATION ON STARTUP               #
# ============================================================================ #
def print_config():
    """Prints the current configuration, redacting sensitive info."""
    print("=" * 50)
    print(f"{APP_NAME} Configuration")
    print("=" * 50)
    print(f"LOG_LEVEL: {LOG_LEVEL}")
    print(f"API_HOST: {API_HOST}")
    print(f"API_PORT: {API_PORT}")
    print(f"CORS_ORIGINS: {CORS_ORIGINS}")
    print("-" * 50)
    print("LLM Settings:")
    print(f"  MODEL_PATH: {MODEL_PATH}")
    print(f"  MAX_TOKENS_GENERATION: {MAX_TOKENS_GENERATION}")
    print(f"  N_CTX: {N_CTX}")
    print(f"  N_GPU_LAYERS: {N_GPU_LAYERS}")
    print("-" * 50)
    print("Redis Settings:")
    print(f"  REDIS_HOST: {REDIS_HOST}")
    print(f"  REDIS_PORT: {REDIS_PORT}")
    print(f"  REDIS_PASSWORD: {'********' if REDIS_PASSWORD else 'Not Set'}")
    print(f"  REDIS_TTL_SECONDS: {REDIS_TTL_SECONDS}")
    print("-" * 50)
    print("Embedding Model Settings:")
    print(f"  EMBEDDING_MODEL_NAME: {EMBEDDING_MODEL_NAME}")
    print(f"  VECTOR_SIMILARITY_THRESHOLD: {VECTOR_SIMILARITY_THRESHOLD}")
    print("=" * 50)

if __name__ == "__main__":
    # This allows running `python backend/config.py` to see current effective settings
    print_config()
