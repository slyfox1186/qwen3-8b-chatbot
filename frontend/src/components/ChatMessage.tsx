import React, { useEffect, useState } from 'react';
import { ChatMessage as ChatMessageType } from '@/types/types';
import MarkdownIt from 'markdown-it';
import '@/styles/ChatMessage.css';
import '@/styles/Markdown.css';

interface ChatMessageProps {
  message: ChatMessageType;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const { role, content, thinking, isInThinkBlock, isThinkingMessage } = message;
  const isUser = role === 'user';
  const [renderedContent, setRenderedContent] = useState<string>('');

  let displayContent = '';
  let prefix = '';

  if (isThinkingMessage) {
    displayContent = thinking || '';
    prefix = isInThinkBlock ? 'Thinking... ' : 'Thoughts: ';
  } else {
    displayContent = content;
    if (thinking && thinking.trim().length > 0) {
        // prefix = "(Reflecting on: " + thinking.trim() + ")\n\n"; 
    }
  }

  if (displayContent === null || displayContent === undefined || displayContent.trim() === '') {
    if (isThinkingMessage && isInThinkBlock) {
      displayContent = '...';
    } else if (role === 'assistant') {
        displayContent = '...'; 
    }
  }
  
  // Initialize markdown-it with options
  useEffect(() => {
    const md = new MarkdownIt({
      html: false,        // Disable HTML tags in source
      xhtmlOut: false,    // Use '/' to close single tags (<br />)
      breaks: true,       // Convert '\n' in paragraphs into <br>
      linkify: true,      // Autoconvert URL-like text to links
      typographer: true,  // Enable smartquotes and other typographic replacements
      highlight: function (str: string, lang: string) {
        // Simple syntax highlighting
        if (lang && lang.length > 0) {
          return `<pre class="language-${lang}"><code>${str}</code></pre>`;
        }
        return `<pre><code>${str}</code></pre>`;
      }
    });
    
    // Render markdown
    const rendered = md.render(displayContent);
    setRenderedContent(rendered);
  }, [displayContent]);

    return (
    <div className={`chat-message ${isUser ? 'user' : 'assistant'} ${isThinkingMessage ? 'thinking-message' : ''} ${isInThinkBlock && isThinkingMessage ? 'active-thinking' : ''}`}>
      <div className="message-role">{isUser ? 'You' : (isThinkingMessage ? 'Assistant (Thinking)' : 'Assistant')}</div>
      <div className="message-content">
        {prefix && <span className="message-prefix-thoughts">{prefix}</span>}
        <div 
          className="markdown-content" 
          dangerouslySetInnerHTML={{ __html: renderedContent }}
        />
      </div>
    </div>
  );
};

export default ChatMessage;