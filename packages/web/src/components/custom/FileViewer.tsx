import { File } from 'lucide-react'
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs'
import type { FileContent } from '../../types'

// Register languages
import html from 'react-syntax-highlighter/dist/esm/languages/hljs/xml'
import css from 'react-syntax-highlighter/dist/esm/languages/hljs/css'
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript'
import markdown from 'react-syntax-highlighter/dist/esm/languages/hljs/markdown'
import plaintext from 'react-syntax-highlighter/dist/esm/languages/hljs/plaintext'

SyntaxHighlighter.registerLanguage('html', html)
SyntaxHighlighter.registerLanguage('css', css)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('markdown', markdown)
SyntaxHighlighter.registerLanguage('plaintext', plaintext)

interface FileViewerProps {
  file: FileContent | null
  isLoading: boolean
}

// Language display names
const LANGUAGE_NAMES: Record<string, string> = {
  html: 'HTML',
  css: 'CSS',
  javascript: 'JavaScript',
  markdown: 'Markdown',
  plaintext: 'Plain Text',
}

const SKELETON_LINE_WIDTHS = [
  88, 72, 96, 83, 90, 77, 94, 81, 86, 73,
  92, 79, 95, 80, 87, 76, 93, 78, 91, 74,
]

export function FileViewer({ file, isLoading }: FileViewerProps) {
  if (isLoading) {
    return <FileViewerSkeleton />
  }

  if (!file) {
    return (
      <div className="file-viewer-empty flex items-center justify-center h-full text-sm text-muted-foreground">
        <div className="text-center space-y-2">
          <File className="h-12 w-12 mx-auto opacity-20" />
          <p>Select a file on the left to view its contents</p>
        </div>
      </div>
    )
  }

  const displayLanguage = LANGUAGE_NAMES[file.language] || file.language

  return (
    <div className="file-viewer flex flex-col h-full">
      <div className="file-header flex items-center justify-between px-4 py-2 bg-muted/30 border-b shrink-0">
        <span className="file-path text-sm font-mono text-muted-foreground truncate">
          {file.path}
        </span>
        <div className="flex items-center gap-3 text-xs text-muted-foreground">
          <span className="px-2 py-0.5 rounded bg-background border">
            {displayLanguage}
          </span>
          <span className="tabular-nums">{formatSize(file.size)}</span>
        </div>
      </div>
      <div className="flex-1 overflow-auto">
        <SyntaxHighlighter
          language={file.language}
          style={docco}
          showLineNumbers
          wrapLongLines
          customStyle={{
            margin: 0,
            borderRadius: 0,
            minHeight: '100%',
            fontSize: '13px',
            fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Monaco, Consolas, monospace',
          }}
          lineNumberStyle={{
            fontSize: '12px',
            color: '#999',
            textAlign: 'right',
            minWidth: '2.5em',
            paddingRight: '1em',
          }}
        >
          {file.content}
        </SyntaxHighlighter>
      </div>
    </div>
  )
}

function FileViewerSkeleton() {
  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 bg-muted/30 border-b shrink-0">
        <div className="h-4 w-48 bg-muted animate-pulse rounded" />
        <div className="flex items-center gap-3">
          <div className="h-5 w-16 bg-muted animate-pulse rounded" />
          <div className="h-4 w-12 bg-muted animate-pulse rounded" />
        </div>
      </div>
      <div className="flex-1 p-4 space-y-2">
        {Array.from({ length: 20 }).map((_, i) => (
          <div
            key={i}
            className="h-4 bg-muted animate-pulse rounded"
            style={{
              width: `${SKELETON_LINE_WIDTHS[i % SKELETON_LINE_WIDTHS.length]}%`,
              animationDelay: `${i * 0.05}s`,
            }}
          />
        ))}
      </div>
    </div>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`
}
