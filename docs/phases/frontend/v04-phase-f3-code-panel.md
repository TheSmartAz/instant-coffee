# Phase F3: CodePanel Component

## Metadata

- **Category**: Frontend
- **Priority**: P1 (Important)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B8 (Files API)
  - **Blocks**: F4

## Goal

Implement the CodePanel component with file tree navigation and syntax-highlighted file viewer for the Code Tab.

## Detailed Tasks

### Task 1: Create FileTree Component

**Description**: Build component for displaying project file structure.

**Implementation Details**:
- [ ] Create FileTree component with tree and onSelectFile props
- [ ] Render nested directory structure
- [ ] Support folder expand/collapse
- [ ] Show file icons based on type (html/css/js/md)
- [ ] Highlight selected file
- [ ] Handle click to select file

**Files to modify/create**:
- `packages/web/src/components/custom/FileTree.tsx` (new)

**Acceptance Criteria**:
- [ ] Tree renders correctly
- [ ] Folders expand/collapse
- [ ] Files selectable
- [ ] Icons distinguish file types

---

### Task 2: Create FileViewer Component

**Description**: Build component for displaying file content with syntax highlighting.

**Implementation Details**:
- [ ] Create FileViewer component with file content props
- [ ] Integrate syntax highlighting library (highlight.js or prism)
- [ ] Display line numbers
- [ ] Handle different languages (html, css, js, markdown)
- [ ] Show empty state when no file selected
- [ ] Read-only (no editing)

**Files to modify/create**:
- `packages/web/src/components/custom/FileViewer.tsx` (new)

**Acceptance Criteria**:
- [ ] Syntax highlighting works
- [ ] Line numbers displayed
- [ ] Scrollable for long files
- [ ] Empty state shown appropriately

---

### Task 3: Create CodePanel Container

**Description**: Build main component that combines FileTree and FileViewer.

**Implementation Details**:
- [ ] Create CodePanel component with sessionId prop
- [ ] Fetch file tree using useFileTree hook
- [ ] Manage selected file state
- [ ] Render FileTree on left, FileViewer on right
- [ ] Handle loading state
- [ ] Handle empty state (no files)

**Files to modify/create**:
- `packages/web/src/components/custom/CodePanel.tsx` (new)

**Acceptance Criteria**:
- [ ] Two-pane layout works
- [ ] File selection updates viewer
- [ ] Loading state handled
- [ ] Responsive layout

---

### Task 4: Create useFileTree Hook

**Description**: Implement hook for fetching file tree and content.

**Implementation Details**:
- [ ] Implement `useFileTree(sessionId)` hook
- [ ] Fetch tree from `GET /api/sessions/{id}/files`
- [ ] Track selected file path
- [ ] Implement `selectFile(path)` that fetches content
- [ ] Fetch content from `GET /api/sessions/{id}/files/{path}`
- [ ] Cache fetched file content

**Files to modify/create**:
- `packages/web/src/hooks/useFileTree.ts` (new)

**Acceptance Criteria**:
- [ ] Tree fetched correctly
- [ ] File content fetched on selection
- [ ] Content cached
- [ ] Error handling works

---

### Task 5: Add File Types

**Description**: Define TypeScript types for file tree.

**Implementation Details**:
- [ ] Create FileTreeNode interface
- [ ] Create FileContent interface
- [ ] Export types from index.ts

**Files to modify/create**:
- `packages/web/src/types/index.ts`

**Acceptance Criteria**:
- [ ] Types match backend schema
- [ ] Types properly exported

---

### Task 6: Add API Client Methods for Files

**Description**: Add methods for file-related API calls.

**Implementation Details**:
- [ ] Add `getFileTree(sessionId): Promise<FileTreeNode[]>`
- [ ] Add `getFileContent(sessionId, path): Promise<FileContent>`
- [ ] Handle URL encoding for paths

**Files to modify/create**:
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] API methods work
- [ ] Path encoding handled
- [ ] Error handling included

---

### Task 7: Style the Code Panel

**Description**: Apply proper styling to file tree and viewer.

**Implementation Details**:
- [ ] Style file tree with proper indentation
- [ ] Add file type icons (📄 📁 or SVG icons)
- [ ] Style selected file highlight
- [ ] Style code viewer with monospace font
- [ ] Add line number gutter
- [ ] Ensure horizontal scroll for long lines
- [ ] Style scrollbars

**Files to modify/create**:
- `packages/web/src/components/custom/CodePanel.tsx`
- `packages/web/src/components/custom/FileTree.tsx`
- `packages/web/src/components/custom/FileViewer.tsx`

**Acceptance Criteria**:
- [ ] Visual design polished
- [ ] File tree readable
- [ ] Code viewer clear
- [ ] Consistent with overall design

---

## Technical Specifications

### FileTree Props

```typescript
interface FileTreeProps {
  tree: FileTreeNode[]
  selectedPath: string | null
  onSelectFile: (path: string) => void
}
```

### FileViewer Props

```typescript
interface FileViewerProps {
  file: FileContent | null
  isLoading: boolean
}
```

### CodePanel Props

```typescript
interface CodePanelProps {
  sessionId: string
}
```

### useFileTree Hook

```typescript
function useFileTree(sessionId: string) {
  return {
    tree: FileTreeNode[]
    selectedFile: FileContent | null
    selectFile: (path: string) => Promise<void>
    isLoading: boolean
  }
}
```

### File Types

```typescript
interface FileTreeNode {
  name: string
  path: string
  type: 'file' | 'directory'
  size?: number
  children?: FileTreeNode[]
}

interface FileContent {
  path: string
  content: string
  language: string  // html, css, javascript, markdown
  size: number
}
```

### FileTree Component

```tsx
function FileTree({ tree, selectedPath, onSelectFile }: FileTreeProps) {
  return (
    <div className="file-tree">
      {tree.map(node => (
        <FileTreeNode
          key={node.path}
          node={node}
          selectedPath={selectedPath}
          onSelectFile={onSelectFile}
          depth={0}
        />
      ))}
    </div>
  )
}

function FileTreeNode({ node, selectedPath, onSelectFile, depth }) {
  const [expanded, setExpanded] = useState(true)

  if (node.type === 'directory') {
    return (
      <div>
        <div
          className="tree-item directory"
          style={{ paddingLeft: depth * 16 }}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? '📂' : '📁'} {node.name}
        </div>
        {expanded && node.children?.map(child => (
          <FileTreeNode
            key={child.path}
            node={child}
            selectedPath={selectedPath}
            onSelectFile={onSelectFile}
            depth={depth + 1}
          />
        ))}
      </div>
    )
  }

  return (
    <div
      className={`tree-item file ${node.path === selectedPath ? 'selected' : ''}`}
      style={{ paddingLeft: depth * 16 }}
      onClick={() => onSelectFile(node.path)}
    >
      {getFileIcon(node.name)} {node.name}
    </div>
  )
}
```

### FileViewer Component

```tsx
import { Light as SyntaxHighlighter } from 'react-syntax-highlighter'
import html from 'react-syntax-highlighter/dist/esm/languages/hljs/xml'
import css from 'react-syntax-highlighter/dist/esm/languages/hljs/css'
import javascript from 'react-syntax-highlighter/dist/esm/languages/hljs/javascript'
import markdown from 'react-syntax-highlighter/dist/esm/languages/hljs/markdown'
import { docco } from 'react-syntax-highlighter/dist/esm/styles/hljs'

SyntaxHighlighter.registerLanguage('html', html)
SyntaxHighlighter.registerLanguage('css', css)
SyntaxHighlighter.registerLanguage('javascript', javascript)
SyntaxHighlighter.registerLanguage('markdown', markdown)

function FileViewer({ file, isLoading }: FileViewerProps) {
  if (isLoading) {
    return <FileViewerSkeleton />
  }

  if (!file) {
    return (
      <div className="file-viewer-empty">
        选择左侧文件查看内容
      </div>
    )
  }

  return (
    <div className="file-viewer">
      <div className="file-header">
        <span className="file-path">{file.path}</span>
        <span className="file-size">{formatSize(file.size)}</span>
      </div>
      <SyntaxHighlighter
        language={file.language}
        style={docco}
        showLineNumbers
        wrapLines
      >
        {file.content}
      </SyntaxHighlighter>
    </div>
  )
}
```

### Styles

```css
.code-panel {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.file-tree {
  width: 240px;
  border-right: 1px solid #e0e0e0;
  overflow-y: auto;
  padding: 8px 0;
}

.tree-item {
  padding: 4px 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
}

.tree-item:hover {
  background: #f5f5f5;
}

.tree-item.selected {
  background: #e3f2fd;
  color: #1976d2;
}

.file-viewer {
  flex: 1;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.file-header {
  padding: 8px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e0e0e0;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #666;
}

.file-viewer-empty {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #999;
}
```

## Testing Requirements

- [ ] Unit tests for FileTree component
- [ ] Unit tests for FileViewer component
- [ ] Unit tests for CodePanel component
- [ ] Unit tests for useFileTree hook
- [ ] Test folder expand/collapse
- [ ] Test file selection
- [ ] Test syntax highlighting
- [ ] Test empty state

## Notes & Warnings

- **Bundle Size**: Syntax highlighting libraries can be large; consider lazy loading
- **Large Files**: May need virtual scrolling for very large files
- **Path Encoding**: Ensure paths with special characters work
- **Language Detection**: Rely on backend language field, not file extension
- **Read-Only**: Explicitly disable any editing functionality
