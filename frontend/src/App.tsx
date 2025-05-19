import React, { useState, useEffect, useRef } from 'react';
import ChatMessage from '@/components/ChatMessage';
import ChatInput from '@/components/ChatInput';
import { ChatMessage as ChatMessageType } from '@/types/types';
import { createConversation, clearConversation } from '@/api/api';
import '@/styles/App.css';

const App: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [convId, setConvId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Refs to manage the state of the current assistant response being built
  const currentThinkingMessageIdRef = useRef<string | null>(null);
  const currentFinalAnswerMessageIdRef = useRef<string | null>(null);
  const streamIsInThinkBlockRef = useRef<boolean>(false); // Tracks if the stream is currently inside <think>...</think>

  // Initialize conversation ID
  useEffect(() => {
    const storedConvId = localStorage.getItem('chatbot_conv_id');
    if (storedConvId) {
      setConvId(storedConvId);
    } else {
      initializeConversation();
    }
  }, []);

  // Scroll to bottom of messages
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const initializeConversation = async () => {
    try {
      const newConvId = await createConversation();
      setConvId(newConvId);
      localStorage.setItem('chatbot_conv_id', newConvId);
    } catch (err) {
      setError('Failed to create a new conversation. Please try again.');
      console.error('Error initializing conversation:', err);
    }
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (message: string) => {
    if (!message.trim()) return;
    
    const userMessageId = `user-${Date.now()}`;
    const userMessage: ChatMessageType = { id: userMessageId, role: 'user', content: message };
    setMessages(prev => [...prev, userMessage]);

    // Reset refs for the new message stream from the assistant
    currentThinkingMessageIdRef.current = null;
    currentFinalAnswerMessageIdRef.current = null;
    streamIsInThinkBlockRef.current = false;
    
    let streamBuffer = ''; // Buffer for the current streaming session for this user message

    try {
      const connection = await import('@/api/api');
      const { streamChat } = connection;

      if (!convId) {
        throw new Error('Conversation ID is not initialized');
      }
      
      streamChat(
        convId,
        message,
        {
          onMessage: (tokenChunkFromServer) => {
            console.log('[TOKEN_DEBUG] Received chunk:', JSON.stringify(tokenChunkFromServer));
            streamBuffer += tokenChunkFromServer;
            let consumedFromBuffer = 0;

            let thinkingTokensInChunk = '';
            let contentTokensInChunk = '';
            let justExitedThinkBlock = false;
            
            console.log('[TOKEN_DEBUG] Current streamBuffer:', JSON.stringify(streamBuffer));
            console.log('[TOKEN_DEBUG] Current thinking state:', streamIsInThinkBlockRef.current);

            while (consumedFromBuffer < streamBuffer.length) {
              // Process tokens based on whether we're in a thinking block or not
              if (streamIsInThinkBlockRef.current) {
                console.log('[TOKEN_DEBUG] In thinking block, looking for </think>');
                const thinkEndPos = streamBuffer.indexOf('</think>', consumedFromBuffer);
                if (thinkEndPos !== -1) {
                  console.log('[TOKEN_DEBUG] Found </think> tag at position', thinkEndPos);
                  const thinkingContent = streamBuffer.substring(consumedFromBuffer, thinkEndPos);
                  console.log('[TOKEN_DEBUG] Thinking content:', JSON.stringify(thinkingContent));
                  thinkingTokensInChunk += thinkingContent;
                  streamIsInThinkBlockRef.current = false;
                  justExitedThinkBlock = true;
                  consumedFromBuffer = thinkEndPos + '</think>'.length;
                  console.log('[TOKEN_DEBUG] Exited thinking block, new consumed position:', consumedFromBuffer);
                } else {
                  console.log('[TOKEN_DEBUG] No </think> tag found, consuming rest of buffer');
                  thinkingTokensInChunk += streamBuffer.substring(consumedFromBuffer);
                  consumedFromBuffer = streamBuffer.length; // Consume rest of buffer
                }
              } else {
                console.log('[TOKEN_DEBUG] Not in thinking block, looking for <think>');
                const thinkStartPos = streamBuffer.indexOf('<think>', consumedFromBuffer);
                if (thinkStartPos !== -1) {
                  console.log('[TOKEN_DEBUG] Found <think> tag at position', thinkStartPos);
                  let potentialContentBeforeThink = streamBuffer.substring(consumedFromBuffer, thinkStartPos);
                  console.log('[TOKEN_DEBUG] Content before <think>:', JSON.stringify(potentialContentBeforeThink));
                  if (potentialContentBeforeThink.trim() !== '[STREAM_COMPLETE]') {
                    contentTokensInChunk += potentialContentBeforeThink;
                  } else {
                    console.log('[TOKEN_DEBUG] Filtered out [STREAM_COMPLETE]');
                  }
                  streamIsInThinkBlockRef.current = true;
                  consumedFromBuffer = thinkStartPos + '<think>'.length;
                  console.log('[TOKEN_DEBUG] Entered thinking block, new consumed position:', consumedFromBuffer);
                } else {
                  console.log('[TOKEN_DEBUG] No <think> tag found, consuming rest of buffer');
                  let potentialContent = streamBuffer.substring(consumedFromBuffer);
                  console.log('[TOKEN_DEBUG] Content without tags:', JSON.stringify(potentialContent));
                  if (potentialContent.trim() !== '[STREAM_COMPLETE]') {
                    contentTokensInChunk += potentialContent;
                  } else {
                    console.log('[TOKEN_DEBUG] Filtered out [STREAM_COMPLETE]');
                  }
                  consumedFromBuffer = streamBuffer.length; // Consume rest of buffer
                }
              }
            }
            streamBuffer = streamBuffer.substring(consumedFromBuffer); // Keep unconsumed part
            
            console.log('[STATE_DEBUG] After processing buffer:');
            console.log('[STATE_DEBUG] thinkingTokensInChunk:', JSON.stringify(thinkingTokensInChunk));
            console.log('[STATE_DEBUG] contentTokensInChunk:', JSON.stringify(contentTokensInChunk));
            console.log('[STATE_DEBUG] justExitedThinkBlock:', justExitedThinkBlock);
            console.log('[STATE_DEBUG] currentThinkingMessageIdRef:', currentThinkingMessageIdRef.current);
            console.log('[STATE_DEBUG] currentFinalAnswerMessageIdRef:', currentFinalAnswerMessageIdRef.current);

            setMessages(prevMessages => {
              let newMessages = [...prevMessages];
              let messageUpdated = false;

              // --- Part 1: Process Thinking Tokens ---
              if (thinkingTokensInChunk.length > 0) {
                console.log('[STATE_DEBUG] Processing thinking tokens...');
                if (currentThinkingMessageIdRef.current) {
                  const msgIndex = newMessages.findIndex(m => m.id === currentThinkingMessageIdRef.current);
                  if (msgIndex !== -1 && newMessages[msgIndex].isThinkingMessage) {
                    newMessages[msgIndex] = {
                      ...newMessages[msgIndex],
                      thinking: (newMessages[msgIndex].thinking || '') + thinkingTokensInChunk,
                      isInThinkBlock: streamIsInThinkBlockRef.current || thinkingTokensInChunk.length > 0, 
                    };
                    messageUpdated = true;
                  } else { currentThinkingMessageIdRef.current = null; } // ID was stale or pointed to non-thinking message
                }
                if (!currentThinkingMessageIdRef.current) { // Create new thinking bubble if needed
                  const newId = `assistant-thinking-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
                  currentThinkingMessageIdRef.current = newId;
                  newMessages.push({
                    id: newId,
                    role: 'assistant',
                    thinking: thinkingTokensInChunk,
                    content: '',
                    isThinkingMessage: true,
                    isInThinkBlock: streamIsInThinkBlockRef.current || thinkingTokensInChunk.length > 0,
                  });
                  messageUpdated = true;
                }
              } else if (justExitedThinkBlock && currentThinkingMessageIdRef.current) {
                // Mark existing thinking bubble as no longer actively streaming thoughts
                const msgIndex = newMessages.findIndex(m => m.id === currentThinkingMessageIdRef.current);
                if (msgIndex !== -1 && newMessages[msgIndex].isThinkingMessage && newMessages[msgIndex].isInThinkBlock) {
                  newMessages[msgIndex].isInThinkBlock = false;
                  messageUpdated = true;
                }
              }

              // --- Part 2: Process Content Tokens ---
              if (contentTokensInChunk.length > 0) {
                console.log('[STATE_DEBUG] Processing content tokens...');
                if (currentFinalAnswerMessageIdRef.current) {
                  const msgIndex = newMessages.findIndex(m => m.id === currentFinalAnswerMessageIdRef.current);
                  if (msgIndex !== -1 && !newMessages[msgIndex].isThinkingMessage) {
                    newMessages[msgIndex] = {
                      ...newMessages[msgIndex],
                      content: (newMessages[msgIndex].content || '') + contentTokensInChunk,
                    };
                    messageUpdated = true;
                  } else { currentFinalAnswerMessageIdRef.current = null; } // ID was stale or pointed to thinking message
                }
                if (!currentFinalAnswerMessageIdRef.current) { // Create new final answer bubble if needed
                  const newId = `assistant-answer-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
                  currentFinalAnswerMessageIdRef.current = newId;
                  newMessages.push({
                    id: newId,
                    role: 'assistant',
                    content: contentTokensInChunk,
                    isThinkingMessage: false,
                  });
                  messageUpdated = true;
                }
              }
              return messageUpdated ? newMessages : prevMessages;
            });
          },
          onError: (errorEvent: Event | Error) => { // Allow Error type for more flexible error handling
            console.error('Stream error:', errorEvent);
            const errorMessage =
              errorEvent instanceof ErrorEvent && errorEvent.message
                ? errorEvent.message
                : errorEvent instanceof Error
                ? errorEvent.message
                : 'Stream connection failed or was interrupted.';
            
            setMessages(prev => {
              const newMessages = [...prev];
              // Try to append error to the last active bubble (thinking or final)
              let targetId = currentFinalAnswerMessageIdRef.current || currentThinkingMessageIdRef.current;
              if (targetId) {
                const msgIndex = newMessages.findIndex(m => m.id === targetId);
                if (msgIndex !== -1) {
                  const targetMsg = newMessages[msgIndex];
                  if (targetMsg.isThinkingMessage) {
                    targetMsg.thinking = (targetMsg.thinking || '') + `\nError: ${errorMessage}`;
                    targetMsg.isInThinkBlock = false; // Stop thinking on error
                  } else {
                    targetMsg.content += `\nError: ${errorMessage}`;
                  }
                  newMessages[msgIndex] = {...targetMsg};
                  return newMessages;
                }
              }
              // If no current assistant message, or ID was stale, add a new error message bubble
              newMessages.push({
                id: `assistant-error-${Date.now()}`,
                role: 'assistant',
                content: `Error: ${errorMessage}`,
                isThinkingMessage: false,
              });
              return newMessages;
            });
            streamIsInThinkBlockRef.current = false; // Ensure this is reset on error
          },
          onEnd: () => {
            console.log('Stream ended.');
            // Finalize thinking bubble state if stream ends while still in think block
            if (streamIsInThinkBlockRef.current && currentThinkingMessageIdRef.current) {
              setMessages(prev => {
                const newMessages = [...prev];
                const msgIndex = newMessages.findIndex(m => m.id === currentThinkingMessageIdRef.current);
                if (msgIndex !== -1 && newMessages[msgIndex].isThinkingMessage && newMessages[msgIndex].isInThinkBlock) {
                  newMessages[msgIndex].isInThinkBlock = false;
                  return newMessages;
                }
                return prev;
              });
            }
            streamIsInThinkBlockRef.current = false; // Reset for safety
          },
        }
      );
    } catch (err) {
      console.error('Failed to send message or establish stream:', err);
      const errorMsg = err instanceof Error ? err.message : 'An unexpected error occurred.';
      setError(`Failed to send message: ${errorMsg}`);
      // Optionally add an error message to the chat display here as well
      setMessages(prev => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          role: 'assistant',
          content: `Error sending message: ${errorMsg}`,
          isThinkingMessage: false,
        },
      ]);
    }
  };

  const handleClearChat = async () => {
    // console.log('=== CLEAR CHAT DEBUG ===');
    // console.log('1. Clear Chat clicked');
    // console.log('2. Current convId:', convId);
    // console.log('3. Current messages length:', messages.length);

    if (!convId) {
      // console.log('4. No convId, returning');
      return;
    }

    try {
      // console.log('5. Making DELETE request to:', `/conversation/${convId}`);
      await clearConversation(convId);
      // console.log('6. Clear request successful');
      setMessages([]);
      // console.log('7. Messages cleared');
      setError(null);
      // console.log('8. Clear chat complete');
    } catch (err) {
      // console.error('9. Error clearing conversation:', err);
      setError('Failed to clear conversation. Please try again.');
    }
  };

  const handleNewChat = async () => {
    // console.log('=== NEW CHAT DEBUG ===');
    // console.log('1. New Chat clicked');
    // console.log('2. Current convId:', convId);

    try {
      // console.log('3. Making POST request to: /conversation');
      // Create a new conversation
      const newConvId = await createConversation();
      // console.log('4. New conversation ID:', newConvId);

      // Update state and localStorage
      setConvId(newConvId);
      // console.log('5. State updated');

      localStorage.setItem('chatbot_conv_id', newConvId);
      // console.log('6. LocalStorage updated');

      // Clear messages
      setMessages([]);
      setError(null);
      // console.log('7. Messages cleared');
      // console.log('8. New chat initialized successfully');
    } catch (err) {
      // console.error('9. Error creating new conversation:', err);
      setError('Failed to create a new conversation. Please try again.');
    }
  };

  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Qwen3-8B Chatbot</h1>
        <div className="header-buttons">
          <button onClick={handleNewChat}>
            New Chat
          </button>
          <button onClick={handleClearChat} disabled={messages.length === 0}>
            Clear Chat
          </button>
        </div>
      </header>
      
      {error && <div className="error-message">{error}</div>}
      
      <div className="messages-container">
        {messages.length === 0 ? (
          <div className="empty-state">
            <p>Start a conversation with the AI assistant</p>
          </div>
        ) : (
          messages.map((message) => (
            <ChatMessage key={message.id} message={message} />
          ))
        )}
        <div ref={messagesEndRef} />
      </div>
      
      <ChatInput onSendMessage={handleSendMessage} disabled={!convId} />
    </div>
  );
};

export default App;