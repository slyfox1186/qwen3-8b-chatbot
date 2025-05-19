import { ChatRequest, ConversationResponse } from '@/types/types';

const API_URL = import.meta.env.VITE_API_URL || '';

export const createConversation = async (): Promise<string> => {
  try {
    console.log('Creating conversation at:', `${API_URL}/conversation`);
    const response = await fetch(`${API_URL}/conversation`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    console.log('Response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response:', errorText);
      throw new Error(`Failed to create conversation: ${response.status} - ${errorText}`);
    }

    const data = await response.json() as ConversationResponse;
    console.log('Created conversation ID:', data.conv_id);
    return data.conv_id;
  } catch (error) {
    console.error('Error creating conversation:', error);
    throw error;
  }
};

export const clearConversation = async (convId: string): Promise<void> => {
  try {
    console.log('Clearing conversation at:', `${API_URL}/conversation/${convId}`);
    const response = await fetch(`${API_URL}/conversation/${convId}`, {
      method: 'DELETE',
    });

    console.log('Response status:', response.status);

    if (!response.ok) {
      const errorText = await response.text();
      console.error('Error response:', errorText);
      throw new Error(`Failed to clear conversation: ${response.status} - ${errorText}`);
    }

    console.log('Conversation cleared successfully');
  } catch (error) {
    console.error('Error clearing conversation:', error);
    throw error;
  }
};

export const getStreamingChatUrl = (convId: string, message: string): string => {
  // Check if the message contains the /no_think command
  const hasNoThinkCommand = message.includes('/no_think');
  
  // Remove the command from the message to avoid confusion
  const cleanedMessage = hasNoThinkCommand ? message.replace('/no_think', '').trim() : message;
  
  // Add a special parameter to explicitly tell the backend to disable thinking mode
  const thinkingModeParam = hasNoThinkCommand ? '&thinking_mode=disabled' : '';
  
  console.log('[API_DEBUG] Sending message with thinking_mode:', hasNoThinkCommand ? 'disabled' : 'enabled');
  
  return `${API_URL}/chat_stream?conv_id=${encodeURIComponent(convId)}&message=${encodeURIComponent(cleanedMessage)}${thinkingModeParam}`;
};

export interface StreamChatCallbacks {
  onMessage: (token: string) => void;
  onError: (error: Event) => void;
  onEnd: () => void;
}

// Custom SSE client implementation for better control and error handling
export const streamChat = (
  convId: string,
  message: string,
  callbacks: StreamChatCallbacks
): { close: () => void } => {
  const url = getStreamingChatUrl(convId, message);
  console.log(`Creating SSE connection for URL: ${url}`);
  
  // Add timeout mechanism to handle missing [END] marker
  let messageTimeoutId: number | null = null;
  const MESSAGE_TIMEOUT_MS = 60000; // 60 seconds
  
  // Function to reset the timeout timer
  const resetMessageTimeout = () => {
    if (messageTimeoutId !== null) {
      window.clearTimeout(messageTimeoutId);
    }
    
    messageTimeoutId = window.setTimeout(() => {
      console.log('No message received for 60 seconds, assuming stream ended');
      callbacks.onEnd();
      if (controller) {
        controller.abort();
      }
    }, MESSAGE_TIMEOUT_MS);
  };

  // Create an AbortController to manage the fetch request
  const controller = new AbortController();
  const { signal } = controller;
  
  // Start the connection
  (async () => {
    try {
      console.log('[API_DEBUG_FETCH_START] Initiating fetch request for SSE...');
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        signal
      });
      console.log(`[API_DEBUG_FETCH_DONE] Fetch response status: ${response.status}`);

      if (!response.ok) {
        console.error(`[API_DEBUG_HTTP_ERROR] HTTP error! status: ${response.status}`);
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      if (!response.body) {
        console.error('[API_DEBUG_NO_BODY] Response body is null!');
        throw new Error('Response body is null');
      }
      console.log('[API_DEBUG_BODY_OK] Response body is present.');
      
      // console.log('SSE connection established successfully');
      resetMessageTimeout();

      const reader = response.body.getReader();
      console.log('[API_DEBUG_READER_OK] Obtained stream reader.');
      
      // Process the stream
      const decoder = new TextDecoder();
      let buffer = '';
      
      console.log('[API_DEBUG_LOOP_START] Starting stream processing loop.');
      while (true) {
        const { done, value } = await reader.read();
        // console.log('[SSE_DEBUG] Raw read result:', { done, value_length: value?.length });
        
        if (done) {
          // console.log('Stream complete');
          if (messageTimeoutId !== null) {
            window.clearTimeout(messageTimeoutId);
            messageTimeoutId = null;
          }
          callbacks.onEnd();
          break;
        }
        
        resetMessageTimeout();
        
        // Decode the chunk and add to buffer
        const rawChunk = decoder.decode(value, { stream: true });
        // console.log('[SSE_DEBUG] Decoded chunk (raw from TextDecoder):', JSON.stringify(rawChunk));

        // Unescape \n and \r in case the server is sending them escaped
        const unescapedChunk = rawChunk.replace(/\\n/g, '\n').replace(/\\r/g, '\r');
        // console.log('[SSE_DEBUG] Decoded chunk (after unescaping):', JSON.stringify(unescapedChunk));
        
        buffer += unescapedChunk; 
        // console.log('[SSE_DEBUG] Buffer after adding chunk:', buffer);
        
        // Process complete messages
        const lines = buffer.split('\n');
        // console.log('[SSE_DEBUG] Buffer split into lines:', lines);
        buffer = lines.pop() || ''; // Keep the last incomplete line in the buffer
        // console.log('[SSE_DEBUG] Buffer after popping last line:', buffer);
        
        for (const line of lines) {
          // console.log('[SSE_DEBUG] Processing line:', line);
          if (line.trim() === '') {
            // console.log('[SSE_DEBUG] Line is empty, skipping.');
            continue;
          }
          
          if (line.startsWith('data: ')) {
            const data = line.substring(6);
            // console.log('[SSE_SUCCESS] SSE message received (data part):', data.substring(0, 100) + (data.length > 100 ? '...' : ''));
            
            if (data === '[END]') {
              // console.log('Received [END] marker, closing connection');
              if (messageTimeoutId !== null) {
                window.clearTimeout(messageTimeoutId);
                messageTimeoutId = null;
              }
              callbacks.onEnd();
              controller.abort();
              return;
            } else {
              // Process each token immediately
              callbacks.onMessage(data);
            }
          } else {
            // console.log('[SSE_DEBUG] Line does not start with "data: ", skipping as SSE message processing.');
          }
        }
      }
    } catch (error) {
      console.log('[API_CATCH_ENTRY] Entered catch block in streamChat.');

      if (error instanceof DOMException && error.name === 'AbortError') {
        console.log('[API_CATCH_ABORT] Error is AbortError (likely timeout or manual close).');
        // Note: timeout mechanism calls callbacks.onEnd() and then aborts.
        // If callbacks.onEnd() was already called by timeout, this path might be expected.
      } else {
        console.error('[API_CATCH_UNEXPECTED_ERROR] Unexpected error in streamChat.');
        // Simplest possible log for the error object to avoid issues with console.error itself:
        console.log('Error object received in catch:', String(error)); 
        if (error instanceof Error && error.stack) {
            console.log('Error stack:', error.stack);
        }
        console.log('[API_CATCH_CALLBACK_PREP] Preparing to call callbacks.onError.');
        callbacks.onError(new Event('stream_error_api_unexpected')); 
      }
    }
  })();
  
  // Return an object with a close method to mimic EventSource API
  return {
    close: () => {
      console.log('Manually closing SSE connection');
      if (messageTimeoutId !== null) {
        window.clearTimeout(messageTimeoutId);
        messageTimeoutId = null;
      }
      controller.abort();
    }
  };
};

export const postChatMessageForStream = async (request: ChatRequest): Promise<Response> => {
  try {
    const response = await fetch(`${API_URL}/chat_stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });
    
    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.status}`);
    }
    
    return response;
  } catch (error) {
    console.error('Error sending message:', error);
    throw error;
  }
};