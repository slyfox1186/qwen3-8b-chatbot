import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = '' }) => {
  // Clean up formatting issues before rendering
  const cleanContent = content
    // Remove any thinking tags that might have slipped through
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/<think>[\s\S]*/g, '') // Handle unclosed think tags
    // Fix headings with ###
    .replace(/(---###|###)\s+(.*?)$/gm, '### $2')
    // Fix quotes
    .replace(/>\s*(\w)/g, '> $1')
    // Fix enumeration in markdown
    .replace(/(\d+)\.\s+/g, '$1. ')
    // Make quoted terms bold
    .replace(/"([^"]+)"/g, '**$1**')
    // Fix common math terms
    .replace(/(\d+)-manifold/g, '**$1-manifold**')
    .replace(/([A-Za-z]+) Conjecture/g, '**$1 Conjecture**')
    .replace(/([A-Za-z]+) Prize/g, '**$1 Prize**');

  return (
    <ReactMarkdown
      className={`markdown-content ${className}`}
      remarkPlugins={[remarkGfm, remarkMath]}
      rehypePlugins={[rehypeRaw, rehypeKatex, rehypeHighlight]}
    >
      {cleanContent}
    </ReactMarkdown>
  );
};

export default MarkdownRenderer;