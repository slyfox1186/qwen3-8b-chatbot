import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';

// Initialize markdown-it with enhanced options for better rendering
const md = new MarkdownIt({
  html: true,        // Enable HTML tags in source
  linkify: true,     // Autoconvert URL-like text to links
  typographer: true, // Enable some language-neutral replacement + quotes beautification
  breaks: true,      // Convert '\n' in paragraphs into <br>
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value;
      } catch (__) {
        // Return empty string on error
      }
    }
    return ''; // Use external default escaping
  }
});

// Function to clean and format markdown text
function preprocessMarkdown(text: string): string {
  // Replace multi-hash sections with proper headers
  text = text.replace(/---###\s+(.*?)$/gm, '### $1');
  text = text.replace(/###\s+(.*?)$/gm, '### $1');
  
  // Format mathematical notation with code blocks
  text = text.replace(/\$\$(.*?)\$\$/g, '`$1`');
  text = text.replace(/\$(.*?)\$/g, '`$1`');
  
  // Format definitions and theorem statements
  text = text.replace(/(\w+) Conjecture \(Statement\):>/g, '**$1 Conjecture (Statement):**');
  text = text.replace(/A (\d+)-manifold/g, 'A **$1-manifold**');
  
  // Clean up "closed", "simply connected" etc. as concepts
  text = text.replace(/"([^"]+)"/g, '**$1**');
  
  return text;
}

/**
 * Renders a Markdown string to HTML.
 * @param markdownText The Markdown string to render.
 * @returns The rendered HTML string.
 */
export function renderMarkdown(markdownText: string): string {
  // Preprocess the markdown to handle special formatting cases
  const processedMarkdown = preprocessMarkdown(markdownText);
  
  // Render processed markdown
  return md.render(processedMarkdown);
}

/**
 * Renders inline Markdown to HTML, without wrapping in <p> tags.
 * @param markdownText The inline Markdown string to render.
 * @returns The rendered HTML string.
 */
export function renderMarkdownInline(markdownText: string): string {
  const processedMarkdown = preprocessMarkdown(markdownText);
  return md.renderInline(processedMarkdown);
}