#!/usr/bin/env python3
# main_async.py (fully async version)

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import uuid4
import os
import asyncio
import logging # Import logging
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime

# Import configuration settings
from . import config

import model
import memory
import utils

# Import web search and route classification
import web_access
import route_classifier

# Set up logging for main.py
logger = logging.getLogger("main_app") # Create a logger instance
logging.basicConfig(level=config.LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Environment variables or defaults
# DEFAULT_SYSTEM_PROMPT = os.getenv(
#     "DEFAULT_SYSTEM_PROMPT", 
#     "You are a helpful assistant."
# )
# CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Print config on startup
    config.print_config()
    # Initialize Redis and vector search on startup
    await memory.initialize()
    yield
    # Cleanup on shutdown
    await memory.close()

# Initialize FastAPI app with lifespan
app = FastAPI(title="Qwen3-8B Chatbot API", lifespan=lifespan)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request models for strong typing
class ChatRequest(BaseModel):
    conv_id: Optional[str] = None
    message: str

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5
    conv_id: Optional[str] = None

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "model": os.path.basename(config.MODEL_PATH)}

# POST version of chat stream endpoint
@app.post("/chat_stream")
async def chat_stream_post(request: ChatRequest) -> StreamingResponse:
    """
    Stream back the assistant's response to a user message.
    Accepts a JSON payload with conversation ID and message.
    """
    conv_id = request.conv_id or str(uuid4())
    user_message = request.message
    thinking_mode = None  # Default to None for POST requests
    
    # Process request and return streaming response
    return await process_chat_request(conv_id, user_message, thinking_mode)

# GET version of chat stream endpoint (for EventSource)
@app.get("/chat_stream")
async def chat_stream_get(
    conv_id: Optional[str] = None,
    message: str = Query(..., description="User message"),
    thinking_mode: Optional[str] = Query(None, description="Control thinking mode (enabled/disabled)")
) -> StreamingResponse:
    """
    Stream back the assistant's response to a user message.
    Accepts query parameters for conversation ID, message, and thinking mode control.
    """
    conv_id = conv_id or str(uuid4())
    
    # Log the thinking_mode parameter
    logger.info(f"Received chat request with thinking_mode: {thinking_mode}")
    
    # Process request and return streaming response
    return await process_chat_request(conv_id, message, thinking_mode)

async def process_chat_request(conv_id: str, user_message: str, thinking_mode: Optional[str] = None) -> StreamingResponse:
    """Process a chat request and return a streaming response"""
    # Get current datetime for injection
    current_time = datetime.now()
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M:%S.%f")

    # Save user message to Redis
    msg_id = await memory.save_message(conv_id, "user", user_message)

    # Index the message for vector search if available
    if memory.is_vector_search_enabled():
        try:
            await memory.index_message(msg_id, "user", user_message, conv_id)
        except Exception as e:
            print(f"Warning: Failed to index message: {str(e)}")

    # Determine if web search is needed
    route_info = await route_classifier.determine_route(user_message)

    # Get conversation history
    conversation = await memory.get_conversation(conv_id)

    # Create time-aware system prompt with thinking mode control
    thinking_mode_directive = ""
    if thinking_mode == "disabled":
        thinking_mode_directive = " /no_think"  # Add the /no_think command to the system prompt
        logger.info(f"Disabling thinking mode for request with message: {user_message}")
    
    time_aware_system_prompt = f"{config.DEFAULT_SYSTEM_PROMPT.format(current_date=current_time.strftime('%Y-%m-%d'))}{thinking_mode_directive}\n\nCurrent date and time: {current_time_str}\nYou have up-to-date information and should provide current answers.\n"

    # Prepare the prompt based on the route
    if route_info["route"] == "WEB":
        cleaned_user_query_for_web_search = route_classifier._clean_query_for_llm(user_message)
        if not cleaned_user_query_for_web_search:
            print("Warning: Query for web search became empty after cleaning commands. Falling back to GENERAL style prompt.")
            prompt = utils.format_chat_prompt(time_aware_system_prompt, conversation)
            citations = ""
        else:
            # Optimize the cleaned query for the search engine
            engine_optimized_query = await route_classifier.optimize_query_for_search(cleaned_user_query_for_web_search)
            logger.info(f"[main.py] Original cleaned query: '{cleaned_user_query_for_web_search}', Engine-optimized query: '{engine_optimized_query}'")

            # Pass both the engine-optimized query (for searching) and the original cleaned query (for context)
            search_result = await web_access.web_search(
                query_for_search_engine=engine_optimized_query, 
                original_cleaned_user_query=cleaned_user_query_for_web_search
            )

            if search_result["success"] and search_result.get("model_prompt"):
                print(f"Web search successful. Using model_prompt from web_access.")
                
                if len(conversation) > 0:
                    messages_for_prompt = conversation[:-1] 
                else:
                    messages_for_prompt = []

                messages_for_prompt.append({
                    "role": "user",
                    "content": search_result["model_prompt"] 
                })
                
                final_system_prompt = f"{time_aware_system_prompt}\nYou have been provided with relevant web search results within the user's message to help answer the query. Please use this information to formulate your response."
                prompt = utils.format_chat_prompt(final_system_prompt, messages_for_prompt)
                citations = search_result.get("citations", "")
            else:
                print("Web search failed or no model_prompt, falling back to general prompt for WEB route.")
                prompt = utils.format_chat_prompt(time_aware_system_prompt, conversation)
                citations = ""
    else:
        # Regular GENERAL route
        prompt = utils.format_chat_prompt(time_aware_system_prompt, conversation)
        citations = ""
    
    # --- BEGIN VERBOSE LOGGING OF FINAL PROMPT ---
    print("\n======================================================================")
    print("                 FINAL PROMPT TO LLM (main.py)                  ")
    print("----------------------------------------------------------------------")
    print(prompt) # This will print the full string representation of the prompt
    print("----------------------------------------------------------------------")
    print(f"LLM Prompt Length: {len(prompt)} characters")
    print("======================================================================\n")
    # --- END VERBOSE LOGGING OF FINAL PROMPT ---

    # Create a generator for SSE streaming
    async def sse_generator() -> AsyncGenerator[str, None]:
        full_response = ""
        # Whether this response uses web data
        has_web_data = route_info["route"] == "WEB" and 'citations' in locals()

        # Send a header to establish SSE connection properly
        yield "retry: 1000\n\n"

        # Variables to track thinking mode (for logging/informational purposes)
        in_thinking_mode = False
        # thinking_buffer has been removed as its purpose was to suppress thinking content.

        try:
            # Stream tokens as SSE events - one token at a time
            async for token in model.generate_stream(prompt):
                if not token:  # Skip empty tokens
                    print("[SSE_DEBUG] Skipping empty token from model.generate_stream")
                    continue

                # Determine if the current token is part of "thinking" for logging purposes
                # and update the overall `in_thinking_mode` state.
                is_currently_thinking_token = False
                if in_thinking_mode: # Was in thinking mode from previous token
                    is_currently_thinking_token = True
                    if "</think>" in token: # This token ends thinking mode
                        print(f"[SSE_DEBUG] Token contains </think>, exiting thinking mode: '{token.encode('unicode_escape').decode('utf-8')}'")
                        in_thinking_mode = False
                        # is_currently_thinking_token remains true for this specific token as it's the concluding part of thinking.
                elif "<think>" in token: # Not in thinking mode, but this token starts it
                    print(f"[SSE_DEBUG] Token contains <think>, entering thinking mode: '{token.encode('unicode_escape').decode('utf-8')}'")
                    in_thinking_mode = True
                    is_currently_thinking_token = True
                
                # All non-empty tokens are now processed for yielding.
                # The original `continue` statements that skipped yielding for thinking mode are removed.

                # Add token to full response and send to client
                full_response += token
                
                log_message = "[SSE_DEBUG] Yielding "
                if is_currently_thinking_token:
                    log_message += "THINKING "
                log_message += f"data token: '{token.encode('unicode_escape').decode('utf-8')}'"
                print(log_message)
                
                yield f"data: {token}\n\n"
                await asyncio.sleep(0.01)

            print(f"[SSE_DEBUG] Loop finished. Full response before citations: '{full_response.encode('unicode_escape').decode('utf-8')}'")
            print("[SSE_DEBUG] Token generation loop completed normally. Yielding [STREAM_COMPLETE].")
            yield "data: [STREAM_COMPLETE]\n\n"
            
        except asyncio.CancelledError:
            logger.warning("SSE generator task was cancelled during token generation.")
            print("[SSE_WARNING] SSE generator task was cancelled during token generation.")
            # If cancelled while thinking, attempt to yield a closing tag for UI consistency
            if in_thinking_mode:
                try:
                    closing_token = "</think>"
                    print(f"[SSE_DEBUG] Attempting to yield closing </think> tag due to cancellation.")
                    full_response += closing_token # For saving later in finally
                    yield f"data: {closing_token}\n\n"
                except Exception as cancel_yield_e:
                    print(f"[SSE_ERROR] Could not yield </think> during cancellation: {type(cancel_yield_e).__name__} - {str(cancel_yield_e)}")
            raise # Re-raise CancelledError, as it's usually handled by the ASGI server
        except Exception as e:
            # Log the error type and message
            error_msg = f"Error during token generation: {type(e).__name__} - {str(e)}"
            logger.error(error_msg, exc_info=True) # Add exc_info for full traceback
            print(f"[SSE_ERROR] {error_msg}")
            
            try:
                # Yield a specific error event to the client
                yield f"data: [ERROR] Server error during stream generation: {type(e).__name__}\n\n"
                
                # If we were in thinking mode when the error occurred, add a closing tag
                if in_thinking_mode:
                    closing_token = "</think>"
                    print(f"[SSE_DEBUG] Adding closing </think> tag due to error: {type(e).__name__}")
                    full_response += closing_token # Add to full_response for saving
                    yield f"data: {closing_token}\n\n"
                
                # Add a generic user-facing error message to the response if it's effectively empty
                # Check if full_response without think tags is empty
                cleaned_response = full_response.replace("<think>", "").replace("</think>", "").strip()
                if not cleaned_response:
                    error_response_text = "I apologize, but I encountered an error while processing your request. Please try again."
                    print(f"[SSE_DEBUG] Adding generic error message to response due to: {type(e).__name__}")
                    full_response += error_response_text # Append for saving
                    yield f"data: {error_response_text}\n\n"
            except Exception as yield_err_e:
                # This catch is for errors during the yielding of error messages itself
                print(f"[SSE_CRITICAL_ERROR] Could not yield error information to client: {type(yield_err_e).__name__} - {str(yield_err_e)}")
            
            # No re-raise here, allow finally to run and send [END]
        finally:
            # This block will always execute, ensuring the [END] marker is sent
            
            # Add citations if we used web search
            if has_web_data and citations:
                print(f"[SSE_DEBUG] Adding citations: '{citations.encode('unicode_escape').decode('utf-8')}'")
                full_response += citations
                yield f"data: {citations}\n\n"

            # Save the complete assistant response to Redis
            try:
                print(f"[SSE_DEBUG] Saving full_response to Redis (length: {len(full_response)} chars).")
                msg_id = await memory.save_message(conv_id, "assistant", full_response)

                # Index the assistant's response for vector search if available
                if memory.is_vector_search_enabled():
                    try:
                        print(f"[SSE_DEBUG] Indexing assistant response.")
                        await memory.index_message(msg_id, "assistant", full_response, conv_id)
                    except Exception as e:
                        print(f"Warning: Failed to index assistant response: {str(e)}")
            except Exception as e:
                print(f"[SSE_ERROR] Failed to save response to Redis: {str(e)}")

            # Always send the [END] marker, even if errors occurred
            print(f"[SSE_DEBUG] In finally block. Yielding [END]. Full response being saved: '{full_response.encode('unicode_escape').decode('utf-8')}'")
            yield "data: [END]\n\n"
            print("[SSE_DEBUG] [END] marker yielded. SSE generator finishing.")

    # Return a streaming response
    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream"
    )

# Endpoint to clear conversation history
@app.delete("/conversation/{conv_id}")
async def clear_conversation(conv_id: str):
    """Clear the conversation history for a given conversation ID"""
    await memory.clear_conversation(conv_id)
    return {"status": "conversation cleared", "conv_id": conv_id}

# Endpoint to create a new conversation ID
@app.post("/conversation")
async def create_conversation():
    """Generate a new conversation ID"""
    conv_id = str(uuid4())
    return {"conv_id": conv_id}

# Memory usage stats endpoint
@app.get("/memory_stats")
async def get_memory_stats():
    """Get Redis memory usage statistics"""
    try:
        stats = await memory.get_redis_memory_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving memory stats: {str(e)}")

# Semantic search endpoint
@app.post("/search")
async def semantic_search(request: SearchRequest):
    """
    Search for messages semantically similar to the query.
    Uses vector similarity search if Redis Stack is available.
    """
    if not memory.is_vector_search_enabled():
        raise HTTPException(
            status_code=501,
            detail="Vector search is not available. Please install Redis Stack."
        )

    try:
        # If conv_id is provided, search only within that conversation
        if request.conv_id:
            results = await memory.search_similar_messages(
                query=request.query,
                limit=request.limit,
                filter_conv_id=request.conv_id
            )
        else:
            # Search across all conversations
            results = await memory.search_similar_messages(
                query=request.query,
                limit=request.limit
            )

        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search error: {str(e)}")

# Get related context endpoint for contextual chat
@app.post("/context")
async def get_context(request: SearchRequest):
    """
    Get relevant context from previous conversations for a query.
    Used to enhance the model's context window with relevant past interactions.
    """
    if not memory.is_vector_search_enabled():
        raise HTTPException(
            status_code=501,
            detail="Vector search is not available. Please install Redis Stack."
        )

    try:
        contexts = await memory.find_context_for_query(
            query=request.query,
            limit=request.limit
        )

        return {"contexts": contexts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Context retrieval error: {str(e)}")

# List user conversations
@app.get("/conversations")
async def list_conversations(user_id: str = "anonymous", limit: int = 10):
    """List all conversations for a user"""
    try:
        conversations = await memory.get_user_conversations(user_id, limit)
        return {"conversations": conversations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing conversations: {str(e)}")

# Route classification endpoint
@app.post("/classify_route")
async def classify_route(request: ChatRequest):
    """
    Classify if a query needs web search or can be answered with general knowledge.
    Returns "WEB" or "GENERAL" route classification.
    """
    route_info = await route_classifier.determine_route(request.message)
    return route_info

# Web search test endpoint
@app.post("/test_web_search")
async def test_web_search(request: SearchRequest):
    """
    Test web search functionality directly without using the model.
    Returns the web search results.
    """
    try:
        search_result = await web_access.web_search(request.query)
        return search_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Web search error: {str(e)}")

# Test direct search function
@app.post("/test_search_function")
async def test_search_function(request: SearchRequest):
    """Test the raw search function without processing results"""
    try:
        # Check if Google API keys are set
        if not (web_access.GOOGLE_API_KEY and web_access.GOOGLE_CSE_KEY):
            return {"error": "Google API keys not configured", "keys_found": False}

        # Call the search_web function directly
        results = await web_access.search_web(request.query, num_results=request.limit or 5)
        return {
            "query": request.query,
            "source": "Google" if web_access.GOOGLE_API_KEY else "DuckDuckGo",
            "results_count": len(results),
            "results": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error testing search function: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)