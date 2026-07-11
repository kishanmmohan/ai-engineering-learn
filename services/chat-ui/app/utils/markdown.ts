import MarkdownIt from 'markdown-it'

// Single shared markdown-it instance. `html: false` keeps raw HTML from the model
// out of the DOM (markdown-it also escapes it), so rendering assistant text is safe.
const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
})

export function renderMarkdown(source: string): string {
  return md.render(source)
}
