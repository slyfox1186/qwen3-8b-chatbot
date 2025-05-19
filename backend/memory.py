import redis.asyncio as redis
import json
import os
import time
import numpy as np
import asyncio
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any, Union
from sentence_transformers import SentenceTransformer
from redis.commands.search.field import TextField, TagField, NumericField, VectorField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query

# Import configuration settings
from . import config

# Redis configuration from environment variables or defaults
REDIS_HOST = config.REDIS_HOST
REDIS_PORT = config.REDIS_PORT
REDIS_PASSWORD = config.REDIS_PASSWORD
REDIS_DB = config.REDIS_DB
REDIS_TTL_SECONDS = config.REDIS_TTL_SECONDS
REDIS_MAX_MEMORY = config.REDIS_MAX_MEMORY
REDIS_MAX_MEMORY_POLICY = config.REDIS_MAX_MEMORY_POLICY

# Initialize async Redis client with optimized configuration
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_PASSWORD,
    db=REDIS_DB,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5,
    retry_on_timeout=True
)

# Constants for storage schema
CONV_HASH_PREFIX = "conv:"        # Stores conversation metadata
MSG_HASH_PREFIX = "msg:"          # Stores individual messages
MSG_LIST_PREFIX = "msgs:"         # Stores message IDs for a conversation
USER_CONVS_PREFIX = "user_convs:" # Stores conversation IDs for a user
VECTOR_KEY_PREFIX = "vector:"     # Stores vector embeddings

# Vector search configuration
VECTOR_INDEX_NAME = config.VECTOR_INDEX_NAME
EMBEDDING_MODEL = config.EMBEDDING_MODEL_NAME
VECTOR_SIMILARITY_THRESHOLD = config.VECTOR_SIMILARITY_THRESHOLD
BGE_QUERY_INSTRUCTION = config.BGE_QUERY_INSTRUCTION

# Initialize vector search capabilities
embedding_model = None
vector_search_enabled = False
vector_dimension = 1024  # Default for BAAI/bge-large-en-v1.5

# Initialize settings on startup
async def initialize():
    """Initialize Redis settings and vector search capabilities"""
    global embedding_model, vector_search_enabled, vector_dimension
    
    # Set server-side memory optimization configurations
    try:
        # Set memory limit and policy
        await redis_client.config_set('maxmemory', REDIS_MAX_MEMORY)
        await redis_client.config_set('maxmemory-policy', REDIS_MAX_MEMORY_POLICY)
        
        # Optimize hash storage for better memory efficiency
        await redis_client.config_set('hash-max-listpack-entries', '512')
        await redis_client.config_set('hash-max-listpack-value', '64')
        
        # Optimize list compression
        await redis_client.config_set('list-max-listpack-size', '8192')
        
        # Enable lazy freeing to avoid blocking operations
        await redis_client.config_set('lazyfree-lazy-eviction', 'yes')
        await redis_client.config_set('lazyfree-lazy-expire', 'yes')
    except redis.exceptions.ResponseError:
        print("Warning: Some Redis optimizations could not be applied")
    
    try:
        # Check if Redis Stack modules are available
        modules = await redis_client.module_list()
        has_search = any(mod.get('name') == 'search' for mod in modules)

        if has_search:
            # Initialize embedding model
            try:
                print(f"Initializing embedding model: {EMBEDDING_MODEL}")
                embedding_model = SentenceTransformer(EMBEDDING_MODEL)
                actual_dimension = embedding_model.get_sentence_embedding_dimension()
                vector_dimension = actual_dimension
                vector_search_enabled = True
                print(f"Embedding model loaded successfully (dimension: {vector_dimension})")

                # Create vector index if it doesn't exist
                try:
                    await redis_client.ft(VECTOR_INDEX_NAME).info()
                    print(f"Vector index '{VECTOR_INDEX_NAME}' already exists.")
                except redis.ResponseError:
                    # Create the index with correct VectorField initialization
                    print(f"Creating vector index '{VECTOR_INDEX_NAME}'...")
                    schema = [
                        TextField("$.content", as_name="content"),
                        TextField("$.role", as_name="role"),
                        TagField("$.conv_id", as_name="conv_id"),
                        NumericField("$.timestamp", as_name="timestamp"),
                        VectorField("$.embedding",
                            "HNSW", {
                                "TYPE": "FLOAT32",
                                "DIM": vector_dimension,
                                "DISTANCE_METRIC": "COSINE"
                            },
                            as_name="embedding"
                        )
                    ]

                    definition = IndexDefinition(
                        prefix=[VECTOR_KEY_PREFIX],
                        index_type=IndexType.JSON
                    )

                    await redis_client.ft(VECTOR_INDEX_NAME).create_index(
                        fields=schema,
                        definition=definition
                    )
                    print(f"Created vector index '{VECTOR_INDEX_NAME}'")
            except Exception as e:
                print(f"Warning: Could not initialize embedding model - {str(e)}")
                embedding_model = None
                vector_search_enabled = False
        else:
            print("Warning: RediSearch module not detected. Vector search will be disabled.")
    except Exception as e:
        print(f"Warning: Vector search initialization error - {str(e)}")
        vector_search_enabled = False

async def save_message(conv_id: str, role: str, content: str, user_id: str = "anonymous") -> str:
    """
    Save a message with memory-optimized structure.
    
    Args:
        conv_id: Conversation identifier
        role: Message role (user/assistant/system)
        content: Message content
        user_id: User identifier (defaults to anonymous)
        
    Returns:
        Message ID
    """
    # Generate unique message ID with microsecond precision
    current_time = datetime.now()
    timestamp_micro = int(time.time() * 1000000)  # Microsecond precision
    msg_id = f"{conv_id}_{timestamp_micro}"

    # Save message data efficiently using Redis hashes
    await redis_client.hset(f"{MSG_HASH_PREFIX}{msg_id}", mapping={
        "role": role,
        "content": content,
        "timestamp": int(time.time()),
        "timestamp_micro": timestamp_micro,
        "datetime_iso": current_time.isoformat(),
        "datetime_readable": current_time.strftime("%Y-%m-%d %H:%M:%S.%f")
    })
    
    # Add message ID to conversation list
    await redis_client.rpush(f"{MSG_LIST_PREFIX}{conv_id}", msg_id)
    
    # Update conversation metadata
    await redis_client.hset(f"{CONV_HASH_PREFIX}{conv_id}", mapping={
        "updated_at": int(time.time()),
        "updated_at_iso": current_time.isoformat(),
        "user_id": user_id
    })
    
    # Increment message count
    await redis_client.hincrby(f"{CONV_HASH_PREFIX}{conv_id}", "message_count", 1)
    
    # Set TTL on all related keys
    await redis_client.expire(f"{MSG_HASH_PREFIX}{msg_id}", REDIS_TTL_SECONDS)
    await redis_client.expire(f"{MSG_LIST_PREFIX}{conv_id}", REDIS_TTL_SECONDS)
    await redis_client.expire(f"{CONV_HASH_PREFIX}{conv_id}", REDIS_TTL_SECONDS)
    
    # Track user conversations
    user_key = f"{USER_CONVS_PREFIX}{user_id}"
    await redis_client.sadd(user_key, conv_id)
    await redis_client.expire(user_key, REDIS_TTL_SECONDS)
    
    return msg_id

async def get_conversation(conv_id: str) -> List[Dict[str, str]]:
    """
    Retrieve conversation messages efficiently.
    
    Args:
        conv_id: Conversation identifier
        
    Returns:
        List of message objects with role and content
    """
    # Get all message IDs for the conversation
    msg_ids = await redis_client.lrange(f"{MSG_LIST_PREFIX}{conv_id}", 0, -1)
    
    if not msg_ids:
        return []
    
    # Use pipeline for efficient batch retrieval
    messages = []
    async with redis_client.pipeline() as pipeline:
        for msg_id in msg_ids:
            pipeline.hgetall(f"{MSG_HASH_PREFIX}{msg_id}")
        
        results = await pipeline.execute()
    
    # Format messages
    for result in results:
        if result:
            messages.append({
                "role": result.get("role", "user"),
                "content": result.get("content", "")
            })
    
    return messages

async def clear_conversation(conv_id: str) -> None:
    """
    Clear conversation history efficiently.
    
    Args:
        conv_id: Conversation identifier
    """
    # Get all message IDs
    msg_ids = await redis_client.lrange(f"{MSG_LIST_PREFIX}{conv_id}", 0, -1)
    
    # Use pipeline for efficient deletion
    async with redis_client.pipeline() as pipeline:
        # Delete each message
        for msg_id in msg_ids:
            pipeline.delete(f"{MSG_HASH_PREFIX}{msg_id}")
        
        # Delete conversation data
        pipeline.delete(f"{MSG_LIST_PREFIX}{conv_id}")
        pipeline.delete(f"{CONV_HASH_PREFIX}{conv_id}")
        
        await pipeline.execute()

async def get_user_conversations(user_id: str = "anonymous", limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get list of conversations for a user.
    
    Args:
        user_id: User identifier
        limit: Maximum number of conversations to return
        
    Returns:
        List of conversation metadata objects
    """
    # Get user's conversation IDs
    conv_ids = await redis_client.smembers(f"{USER_CONVS_PREFIX}{user_id}")
    
    if not conv_ids:
        return []
    
    # Retrieve conversation metadata
    conversations = []
    for conv_id in conv_ids:
        data = await redis_client.hgetall(f"{CONV_HASH_PREFIX}{conv_id}")
        if data:
            # Convert timestamps and counts to appropriate types
            data["updated_at"] = int(data.get("updated_at", 0))
            data["message_count"] = int(data.get("message_count", 0))
            data["id"] = conv_id
            conversations.append(data)
    
    # Sort by last updated time (descending)
    conversations.sort(key=lambda x: x["updated_at"], reverse=True)
    
    # Return limited number of results
    return conversations[:limit]

async def get_redis_memory_stats() -> Dict[str, Union[str, int]]:
    """
    Get Redis memory usage statistics.

    Returns:
        Dictionary with memory usage information
    """
    info = await redis_client.info("memory")
    return {
        "used_memory_human": info.get("used_memory_human", "unknown"),
        "used_memory_peak_human": info.get("used_memory_peak_human", "unknown"),
        "maxmemory_human": info.get("maxmemory_human", "unknown"),
        "maxmemory_policy": info.get("maxmemory_policy", "unknown"),
        "mem_fragmentation_ratio": info.get("mem_fragmentation_ratio", 0)
    }

async def generate_embedding(text: str, is_query: bool = False) -> Optional[List[float]]:
    """
    Generate an embedding vector for the given text.

    Args:
        text: The text to generate an embedding for
        is_query: Whether this is a query (adds BGE instruction prefix)

    Returns:
        A list of floats representing the embedding vector, or None if generation fails
    """
    if not vector_search_enabled or embedding_model is None:
        return None

    try:
        # For BGE model, add instruction prefix for queries
        if is_query:
            text = f"{BGE_QUERY_INSTRUCTION} {text}"

        # Generate embedding with normalization (recommended for BGE)
        # Run in executor since it's CPU-bound
        embedding = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: embedding_model.encode(text, normalize_embeddings=True)
        )
        return embedding.tolist()
    except Exception as e:
        print(f"Error generating embedding: {str(e)}")
        return None

async def index_message(msg_id: str, role: str, content: str, conv_id: str) -> bool:
    """
    Index a message for vector search.

    Args:
        msg_id: Message identifier
        role: Message role ("user" or "assistant")
        content: Message content
        conv_id: Conversation identifier

    Returns:
        True if indexing was successful, False otherwise
    """
    if not vector_search_enabled:
        return False

    try:
        # Generate embedding (don't use query instruction for stored messages)
        embedding = await generate_embedding(content, is_query=False)
        if embedding is None:
            return False

        # Store the embedding with message metadata
        vector_key = f"{VECTOR_KEY_PREFIX}{msg_id}"
        timestamp = int(time.time())

        # Store as JSON document for Redis Stack
        await redis_client.json().set(vector_key, '$', {
            'id': msg_id,
            'content': content,
            'role': role,
            'conv_id': conv_id,
            'timestamp': timestamp,
            'embedding': embedding
        })

        # Set expiration time to match conversation TTL
        await redis_client.expire(vector_key, REDIS_TTL_SECONDS)

        return True
    except Exception as e:
        print(f"Error indexing message: {str(e)}")
        return False

async def search_similar_messages(query: str, limit: int = 5,
                                filter_conv_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Search for messages similar to the query text using vector similarity.

    Args:
        query: The query text
        limit: Maximum number of results to return
        filter_conv_id: Optional conversation ID to filter results

    Returns:
        List of message objects with similarity scores
    """
    if not vector_search_enabled:
        return []

    try:
        # Generate embedding for the query (with BGE instruction)
        query_embedding = await generate_embedding(query, is_query=True)
        if query_embedding is None:
            return []

        # Build query
        base_query = f"*=>[KNN {limit} @embedding $BLOB AS score]"

        # Add filter if specified
        if filter_conv_id:
            query_str = f"@conv_id:{{{filter_conv_id}}} {base_query}"
        else:
            query_str = base_query

        # Convert embedding to bytes for Redis
        query_vector = np.array(query_embedding, dtype=np.float32).tobytes()

        # Execute vector search
        q = Query(query_str).return_fields("content", "role", "conv_id", "timestamp", "score").dialect(2)

        results = await redis_client.ft(VECTOR_INDEX_NAME).search(
            q,
            query_params={"BLOB": query_vector}
        )

        # Format results
        messages = []
        for doc in results.docs:
            score = float(doc.score)
            # Only include results above similarity threshold
            if score >= VECTOR_SIMILARITY_THRESHOLD:
                messages.append({
                    'id': doc.id.split(':')[-1],  # Extract ID from key
                    'content': doc.content,
                    'role': doc.role,
                    'conv_id': doc.conv_id,
                    'timestamp': int(doc.timestamp),
                    'similarity': score
                })

        return messages
    except Exception as e:
        print(f"Error searching messages: {str(e)}")
        return []

async def find_context_for_query(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """
    Find relevant context across all conversations for a query.
    This is useful for providing context to the model from past interactions.

    Args:
        query: The query text
        limit: Maximum number of results to return

    Returns:
        List of message objects with conversation context
    """
    # First search for similar messages
    similar_messages = await search_similar_messages(query, limit=limit)

    if not similar_messages:
        return []

    # For each similar message, get conversation context
    results = []
    for msg in similar_messages:
        conv_id = msg.get('conv_id')
        if conv_id:
            # Get a few messages around this one for context
            conversation = await get_conversation(conv_id)

            # Add conversation reference to the result
            msg['context'] = conversation
            results.append(msg)

    return results

def is_vector_search_enabled() -> bool:
    """
    Check if vector search capability is enabled.

    Returns:
        True if vector search is enabled, False otherwise
    """
    return vector_search_enabled

# Close the Redis connection when done
async def close():
    """Close the Redis connection"""
    await redis_client.close()