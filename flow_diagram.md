# Complete Flow Diagram: From User Input to Token Streaming

This document provides a comprehensive step-by-step explanation of how the Qwen3-8B chatbot application works, from the moment a user inputs a query to the final display of the streamed response.

## Table of Contents
1. [System Architecture Overview](#system-architecture-overview)
2. [Detailed Flow Diagram](#detailed-flow-diagram)
3. [Step-by-Step Process Explanation](#step-by-step-process-explanation)
4. [Key Components](#key-components)
5. [Data Flow](#data-flow)
6. [Error Handling](#error-handling)
7. [Optimization Techniques](#optimization-techniques)

## System Architecture Overview

The application follows a client-server architecture with the following main components:

- **Frontend**: React application with TypeScript
- **Backend**: FastAPI server with Python
- **Model**: Qwen3-8B language model using llama-cpp-python
- **Database**: Redis for conversation memory and vector search

## Detailed Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                                       FRONTEND                                                                       │
│                                                                                                                                     │
│  ┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌────────────────────┐     ┌────────────────┐     ┌─────────────┐  │
│  │ User inputs │     │ ChatInput.tsx│     │                │     │                    │     │                │     │             │  │
│  │   query     │────▶│ captures and │────▶│    App.tsx     │────▶│     api.ts        │────▶│  ChatMessage   │────▶│  Displayed  │  │
│  │             │     │ sends message│     │ handleSendMsg  │     │ streamChat/fetch  │     │  component     │     │  to user    │  │
│  └─────────────┘     └──────────────┘     └────────────────┘     └────────────────────┘     └────────────────┘     └─────────────┘  │
│                                                  │  ▲                      │  ▲                      ▲                               │
└──────────────────────────────────────────────────┼──┼──────────────────────┼──┼──────────────────────┼───────────────────────────────┘
                                                   │  │                      │  │                      │
                                                   │  │                      │  │                      │
                                                   │  │                      │  │                      │
┌──────────────────────────────────────────────────┼──┼──────────────────────┼──┼──────────────────────┼───────────────────────────────┐
│                                                  │  │                      │  │                      │                               │
│                                                  ▼  │                      ▼  │                      │                               │
│  ┌─────────────┐     ┌──────────────┐     ┌────────────────┐     ┌────────────────────┐     ┌────────────────┐                      │
│  │ FastAPI     │     │ main.py      │     │                │     │                    │     │                │                      │
│  │ Endpoints   │────▶│ process_chat │────▶│    model.py    │────▶│ SSE Generator      │────▶│  Token Stream  │                      │
│  │             │     │ _request     │     │ generate_stream│     │ sse_generator      │     │  back to client│                      │
│  └─────────────┘     └──────────────┘     └────────────────┘     └────────────────────┘     └────────────────┘                      │
│                                                  │                         │                                                         │
│                                                  ▼                         │                                                         │
│                                           ┌────────────────┐               │                                                         │
│                                           │   memory.py    │               │                                                         │
│                                           │ save_message   │               │                                                         │
│                                           │ index_message  │               │                                                         │
│                                           └────────────────┘               │                                                         │
│                                                  │                         │                                                         │
│                                                  ▼                         │                                                         │
│                                           ┌────────────────┐               │                                                         │
│                                           │ route_classifier│               │                                                         │
│                                           │ determine_route│               │                                                         │
│                                           └────────────────┘               │                                                         │
│                                                  │                         │                                                         │
│                                                  ▼                         │                                                         │
│                                           ┌────────────────┐               │                                                         │
│                                           │  web_access.py │               │                                                         │
│                                           │  (if needed)   │───────────────┘                                                         │
│                                           └────────────────┘                                                                         │
│                                                                                                                                     │
│                                                       BACKEND                                                                        │
└─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Step-by-Step Process Explanation

### 1. User Input Capture
1. User types a message in the chat input field
2. The `ChatInput.tsx` component captures the input and calls `onSendMessage` when submitted
3. The input is passed to the parent `App.tsx` component's `handleSendMessage` function

### 2. Frontend Message Processing
1. `App.tsx` creates a new user message object and adds it to the messages state
2. It sets the `isStreaming` state to true to disable the input field
3. It creates a new assistant message object with empty content as a placeholder
4. It calls the `streamChat` function from `api.ts` to initiate the API request

### 3. API Request Initialization
1. `api.ts` constructs the API URL with the conversation ID and user message
2. It checks for special commands like `/no_think` and adds appropriate parameters
3. It initializes a custom fetch-based SSE client to handle streaming
4. It sets up callbacks for message tokens, errors, and stream end events

### 4. Backend Request Handling
1. FastAPI receives the request at the `/chat_stream` endpoint in `main.py`
2. The `chat_stream_get` or `chat_stream_post` function processes the request
3. It calls `process_chat_request` with the conversation ID, user message, and thinking mode

### 5. Conversation Memory Management
1. `process_chat_request` gets the current datetime for injection
2. It saves the user message to Redis using `memory.save_message`
3. If vector search is enabled, it indexes the message for future retrieval

### 6. Route Classification
1. `route_classifier.determine_route` analyzes the user message
2. It decides if the query needs web search or can be answered with general knowledge
3. If web search is needed, `web_access.web_search` is called to retrieve information

### 7. Context Retrieval
1. The system retrieves conversation history from Redis
2. It formats the history into a list of message dictionaries
3. If relevant, it adds web search results to the context

### 8. Model Inference
1. `model.py` receives the formatted prompt with conversation history
2. It processes any special commands like `/think` or `/no_think`
3. It initializes the Qwen3-8B model via llama-cpp-python
4. It calls `generate_stream` to start token generation

### 9. Token Streaming (Backend to Frontend)
1. `_generate` function creates a thread to run the model inference
2. `_stream_tokens` iterates through the generated tokens
3. Each token is put into an async queue
4. The `sse_generator` function yields tokens from the queue as SSE events
5. FastAPI's `StreamingResponse` sends these events to the client

### 10. Frontend Token Processing
1. The custom SSE client in `api.ts` receives the token stream
2. It processes each token and calls the `onMessage` callback
3. `App.tsx` receives each token and updates the message state
4. It parses special tags like `<think>` and `</think>` to separate thinking from content
5. It updates the appropriate message in the messages array

### 11. UI Rendering
1. React re-renders the UI with the updated messages state
2. `ChatMessage.tsx` renders each message based on its role and content
3. It uses `MarkdownRenderer` to format the content with markdown
4. It shows "Assistant (Thinking)" for thinking messages and "Assistant" for regular responses

### 12. Stream Completion
1. When the backend sends an `[END]` marker, the stream is considered complete
2. The `onEnd` callback is triggered in `api.ts`
3. `App.tsx` sets `isStreaming` to false, enabling the input field again
4. The final message is displayed with complete content

## Key Components

### Frontend Components
- **App.tsx**: Main application component that manages state and coordinates the chat flow
- **ChatInput.tsx**: Handles user input capture and submission
- **ChatMessage.tsx**: Renders individual chat messages with proper formatting
- **MarkdownRenderer.tsx**: Formats message content with markdown
- **api.ts**: Manages API communication and SSE streaming

### Backend Components
- **main.py**: FastAPI server with endpoints for chat, conversation management, and utilities
- **model.py**: Handles model initialization and inference
- **memory.py**: Manages conversation storage and retrieval in Redis
- **route_classifier.py**: Determines if a query needs web search
- **web_access.py**: Handles web search functionality
- **utils.py**: Utility functions for prompt formatting and other helpers

## Data Flow

### Message Object Structure
```typescript
interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  thinking?: string;
  isThinkingMessage?: boolean;
  isInThinkBlock?: boolean;
}
```

### Token Stream Format
The backend streams tokens in plain text format with special tags:
- `<think>`: Marks the beginning of thinking content
- `</think>`: Marks the end of thinking content
- `[END]`: Marks the end of the stream

## Error Handling

1. **Connection Interruptions**:
   - A timeout mechanism detects if no tokens are received for 60 seconds
   - If the timeout triggers, the stream is considered ended
   - The UI shows an error message if appropriate

2. **Model Errors**:
   - Errors during model inference are caught and logged
   - Error messages are sent to the client as special tokens
   - The frontend displays appropriate error messages

3. **Redis Failures**:
   - The system gracefully handles Redis connection issues
   - If vector search is unavailable, it falls back to basic conversation history

## Optimization Techniques

1. **Token-by-Token Streaming**:
   - Tokens are streamed immediately as they're generated
   - This provides a responsive user experience with minimal latency

2. **Custom SSE Client**:
   - A fetch-based SSE client replaces the native EventSource
   - This provides better control over connection handling and error recovery

3. **Buffer Management**:
   - The frontend maintains a buffer to handle tokens that might be split across chunks
   - This ensures proper parsing of special tags like `<think>` and `</think>`

4. **GPU Acceleration**:
   - The model uses GPU acceleration via llama-cpp-python
   - This significantly improves inference speed and responsiveness

5. **Vector Search**:
   - Redis is used for vector similarity search
   - This enables contextual retrieval of relevant past conversations
