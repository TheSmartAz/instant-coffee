# Design System Implementation Plan

## Overview

This document outlines the implementation plan for the Instant Coffee web application frontend. The plan is organized into phases, with dependencies clearly marked.

**Tech Stack:**
- React 19 + Vite
- TypeScript
- Tailwind CSS v4
- shadcn/ui (new-york style)
- react-resizable-panels
- react-router-dom (to be added)

**Reference:** See `docs/design-system.md` for design tokens and specifications.

---

## Phase 1: Foundation (COMPLETED)

### 1.1 Project Setup
- [x] Vite + React + TypeScript
- [x] Tailwind CSS v4 configuration
- [x] Path aliases (`@/*` → `src/*`)
- [x] shadcn/ui configuration (`components.json`)

### 1.2 Design Tokens
- [x] CSS variables in `src/index.css`
- [x] Tailwind theme extension in `tailwind.config.js`
- [x] Inter font import

### 1.3 Core UI Components (shadcn)
- [x] Button (primary, secondary, outline, ghost)
- [x] Input
- [x] Card
- [x] Avatar
- [x] ScrollArea
- [x] Separator
- [x] Resizable (Panel, Handle)
- [x] Collapsible
- [x] Tooltip

---

## Phase 2: Additional shadcn Components

Add remaining shadcn components needed for the app.

### 2.1 Form Components
```bash
npx shadcn@latest add textarea
npx shadcn@latest add select
npx shadcn@latest add slider
npx shadcn@latest add label
npx shadcn@latest add switch
```

### 2.2 Feedback Components
```bash
npx shadcn@latest add dialog
npx shadcn@latest add alert-dialog
npx shadcn@latest add toast
npx shadcn@latest add sonner
```

### 2.3 Navigation Components
```bash
npx shadcn@latest add dropdown-menu
npx shadcn@latest add tabs
```

### 2.4 Data Display
```bash
npx shadcn@latest add badge
npx shadcn@latest add skeleton
```

**After each install:** Fix import path from `src/lib/utils` to `@/lib/utils`

---

## Phase 3: Custom Components

Build custom components on top of shadcn primitives.

### 3.1 PhoneFrame
**Location:** `src/components/custom/PhoneFrame.tsx`

**Purpose:** Realistic iPhone-style device frame for preview panel

**Props:**
```typescript
interface PhoneFrameProps {
  children: React.ReactNode
  className?: string
  scale?: number // 0.5 - 1.0, default 1
}
```

**Features:**
- iPhone 15 Pro Max style bezel
- Dynamic Island notch
- 9:19.5 aspect ratio
- Content rendered via children (iframe or div)
- Optional scale for responsive sizing

**Implementation Notes:**
- Use CSS for device frame (border-radius, shadows)
- Inner content area: 430px max-width
- Add subtle reflection/gloss effect

---

### 3.2 ProjectCard
**Location:** `src/components/custom/ProjectCard.tsx`

**Purpose:** Gallery card showing project with mini phone preview

**Props:**
```typescript
interface ProjectCardProps {
  id: string
  name: string
  thumbnail?: string // Screenshot URL or base64
  updatedAt: Date
  versionCount: number
  onClick?: () => void
}
```

**Features:**
- Mini PhoneFrame showing thumbnail
- Project name below
- Relative timestamp ("2 hours ago")
- Hover state with shadow elevation
- Click to navigate to project

**Dependencies:** PhoneFrame, Card

---

### 3.3 ChatMessage
**Location:** `src/components/custom/ChatMessage.tsx`

**Purpose:** Full-width message component (ChatGPT style)

**Props:**
```typescript
interface ChatMessageProps {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
  isStreaming?: boolean
}
```

**Features:**
- Full-width layout
- Alternating background (white / muted)
- Avatar on left (32px)
- Support for markdown rendering
- Streaming indicator (typing dots)
- Code block syntax highlighting

**Dependencies:** Avatar, ScrollArea

---

### 3.4 ChatInput
**Location:** `src/components/custom/ChatInput.tsx`

**Purpose:** Message input with send button

**Props:**
```typescript
interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
  placeholder?: string
}
```

**Features:**
- Auto-expanding textarea
- Send button (icon or text)
- Keyboard shortcut: Enter to send, Shift+Enter for newline
- Disabled state during streaming

**Dependencies:** Textarea, Button

---

### 3.5 VersionTimeline
**Location:** `src/components/custom/VersionTimeline.tsx`

**Purpose:** Vertical timeline showing version history

**Props:**
```typescript
interface Version {
  id: string
  number: number
  createdAt: Date
  isCurrent: boolean
}

interface VersionTimelineProps {
  versions: Version[]
  onSelect: (versionId: string) => void
  onRevert?: (versionId: string) => void
}
```

**Features:**
- Vertical line with dots
- Current version: filled accent dot
- Past versions: outline dots
- Relative timestamps
- Click to preview, button to revert
- Scrollable if many versions

**Dependencies:** ScrollArea, Button

---

### 3.6 ChatPanel
**Location:** `src/components/custom/ChatPanel.tsx`

**Purpose:** Complete chat panel with messages and input

**Props:**
```typescript
interface ChatPanelProps {
  messages: Message[]
  onSendMessage: (content: string) => void
  isLoading?: boolean
}
```

**Features:**
- Header with project context
- Scrollable message list
- Auto-scroll to bottom on new messages
- ChatInput at bottom
- Loading state

**Dependencies:** ChatMessage, ChatInput, ScrollArea

---

### 3.7 PreviewPanel
**Location:** `src/components/custom/PreviewPanel.tsx`

**Purpose:** Preview panel with phone frame and controls

**Props:**
```typescript
interface PreviewPanelProps {
  htmlContent: string
  onRefresh?: () => void
  onExport?: () => void
}
```

**Features:**
- Centered PhoneFrame
- Toolbar with refresh/export buttons
- iframe for rendering HTML content
- Responsive scaling based on panel size

**Dependencies:** PhoneFrame, Button

---

### 3.8 VersionPanel
**Location:** `src/components/custom/VersionPanel.tsx`

**Purpose:** Collapsible version control panel

**Props:**
```typescript
interface VersionPanelProps {
  versions: Version[]
  currentVersionId: string
  onSelectVersion: (id: string) => void
  onRevertVersion: (id: string) => void
  isCollapsed: boolean
  onToggleCollapse: () => void
}
```

**Features:**
- Collapsible (280px expanded, 48px collapsed)
- Collapse button with icon
- VersionTimeline when expanded
- Just icons when collapsed

**Dependencies:** VersionTimeline, Collapsible, Button

---

## Phase 4: Page Layouts

### 4.1 Setup Routing
```bash
npm install react-router-dom
```

**Router Configuration:** `src/main.tsx`
```typescript
import { BrowserRouter } from 'react-router-dom'

// Wrap App with BrowserRouter
```

**Routes:** `src/App.tsx`
```typescript
<Routes>
  <Route path="/" element={<HomePage />} />
  <Route path="/project/:id" element={<ProjectPage />} />
  <Route path="/settings" element={<SettingsPage />} />
</Routes>
```

---

### 4.2 HomePage
**Location:** `src/pages/HomePage.tsx`

**Layout:**
```
┌─────────────────────────────────────────┐
│              [Logo]                     │
│                                         │
│    ┌─────────────────────────────┐      │
│    │  What would you like to     │      │
│    │  create today?              │      │
│    │  [________________________] │      │
│    │         [Create →]          │      │
│    └─────────────────────────────┘      │
│                                         │
│  Your Projects                          │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐               │
│  │📱│ │📱│ │📱│ │📱│               │
│  └───┘ └───┘ └───┘ └───┘               │
└─────────────────────────────────────────┘
```

**Components Used:**
- Input (hero section)
- Button (create button)
- ProjectCard (gallery grid)

**State:**
- `projects: Project[]` - List of user projects
- `inputValue: string` - Hero input value

**API Calls:**
- `GET /api/sessions` - Fetch projects on mount
- `POST /api/sessions` - Create new project

---

### 4.3 ProjectPage
**Location:** `src/pages/ProjectPage.tsx`

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│  ← Back    Project Name                     [⚙ Settings]│
├─────────────║───────────────────║───────────────────────┤
│             ║                   ║  Versions             │
│  ChatPanel  ║   PreviewPanel    ║  VersionPanel         │
│  (resize)   ║   (resize)        ║  (collapse)           │
└─────────────║───────────────────║───────────────────────┘
```

**Components Used:**
- ResizablePanelGroup, ResizablePanel, ResizableHandle
- ChatPanel
- PreviewPanel
- VersionPanel
- Button (back, settings)

**State:**
- `session: Session` - Current session data
- `messages: Message[]` - Chat messages
- `versions: Version[]` - Version history
- `currentHtml: string` - Current preview HTML
- `isVersionPanelCollapsed: boolean`

**API Calls:**
- `GET /api/sessions/:id` - Fetch session
- `GET /api/sessions/:id/messages` - Fetch messages
- `GET /api/sessions/:id/versions` - Fetch versions
- `POST /api/chat` - Send message (SSE streaming)
- `POST /api/sessions/:id/versions/:versionId/revert` - Revert version

---

### 4.4 SettingsPage
**Location:** `src/pages/SettingsPage.tsx`

**Layout:**
```
┌──────────┬──────────────────────────────────┐
│          │                                  │
│ Account  │  [Section Content]               │
│ Model ●  │                                  │
│ Prefs    │                                  │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

**Sections:**

**Account:**
- API key input (masked)
- Save button

**Model:**
- Model selection dropdown (Claude Sonnet 4, etc.)
- Temperature slider (0.0 - 1.0)
- Max tokens input

**Preferences:**
- Output directory path
- Auto-save toggle

**Components Used:**
- Tabs or custom sidebar navigation
- Input, Select, Slider, Switch
- Button (save)
- Card (section containers)

**State:**
- `settings: Settings` - Current settings
- `activeSection: string` - Current tab/section

**API Calls:**
- `GET /api/settings` - Fetch settings
- `PUT /api/settings` - Update settings

---

## Phase 5: State Management & API Integration

### 5.1 API Client
**Location:** `src/api/client.ts`

```typescript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = {
  sessions: {
    list: () => fetch(`${API_BASE}/api/sessions`),
    get: (id: string) => fetch(`${API_BASE}/api/sessions/${id}`),
    create: (data: CreateSessionData) => fetch(...),
    // ...
  },
  chat: {
    send: (sessionId: string, message: string) => {
      // SSE streaming implementation
    }
  },
  // ...
}
```

### 5.2 Custom Hooks
**Location:** `src/hooks/`

| Hook | Purpose |
|------|---------|
| `useProjects()` | Fetch and manage projects list |
| `useSession(id)` | Fetch single session with messages/versions |
| `useChat(sessionId)` | Send messages, handle streaming |
| `useSettings()` | Fetch and update settings |

### 5.3 SSE Streaming
**Location:** `src/hooks/useChat.ts`

Handle Server-Sent Events for streaming responses:
```typescript
const eventSource = new EventSource(`${API_BASE}/api/chat/stream?session_id=${sessionId}`)
eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data)
  // Update message content progressively
}
```

---

## Phase 6: Polish & Optimization

### 6.1 Loading States
- Skeleton loaders for ProjectCard grid
- Typing indicator for chat
- Spinner for version operations

### 6.2 Error Handling
- Toast notifications for errors
- Retry logic for failed requests
- Offline state handling

### 6.3 Animations
- Page transitions
- Panel resize animations
- Message appear animations

### 6.4 Accessibility
- Keyboard navigation
- Focus management
- ARIA labels
- Screen reader support

### 6.5 Performance
- Virtualized lists for long chat history
- Lazy loading for project thumbnails
- Debounced inputs

---

## Implementation Order

### Wave 1: Foundation
1. ✅ Phase 1 (Complete)
2. Phase 2.1-2.4 (Add shadcn components)

### Wave 2: Core Components
3. Phase 3.1 (PhoneFrame)
4. Phase 3.2 (ProjectCard)
5. Phase 3.3-3.4 (ChatMessage, ChatInput)
6. Phase 3.5 (VersionTimeline)

### Wave 3: Composite Components
7. Phase 3.6 (ChatPanel)
8. Phase 3.7 (PreviewPanel)
9. Phase 3.8 (VersionPanel)

### Wave 4: Pages
10. Phase 4.1 (Routing setup)
11. Phase 4.2 (HomePage)
12. Phase 4.3 (ProjectPage)
13. Phase 4.4 (SettingsPage)

### Wave 5: Integration
14. Phase 5.1-5.3 (API & State)
15. Phase 6 (Polish)

---

## File Structure (Target)

```
src/
├── api/
│   └── client.ts
├── components/
│   ├── custom/
│   │   ├── ChatInput.tsx
│   │   ├── ChatMessage.tsx
│   │   ├── ChatPanel.tsx
│   │   ├── PhoneFrame.tsx
│   │   ├── PreviewPanel.tsx
│   │   ├── ProjectCard.tsx
│   │   ├── VersionPanel.tsx
│   │   └── VersionTimeline.tsx
│   └── ui/
│       ├── avatar.tsx
│       ├── button.tsx
│       ├── card.tsx
│       ├── ... (shadcn components)
│       └── tooltip.tsx
├── hooks/
│   ├── useChat.ts
│   ├── useProjects.ts
│   ├── useSession.ts
│   └── useSettings.ts
├── lib/
│   └── utils.ts
├── pages/
│   ├── HomePage.tsx
│   ├── ProjectPage.tsx
│   └── SettingsPage.tsx
├── types/
│   └── index.ts
├── App.tsx
├── index.css
└── main.tsx
```

---

## Dependencies to Add

```bash
# Routing
npm install react-router-dom

# Markdown rendering (for chat messages)
npm install react-markdown remark-gfm

# Date formatting
npm install date-fns

# Optional: State management (if needed)
npm install zustand
# or
npm install @tanstack/react-query
```

---

## Testing Strategy

### Unit Tests
- Custom components (PhoneFrame, ChatMessage, etc.)
- Hooks (useChat, useProjects, etc.)
- Utility functions

### Integration Tests
- Page rendering with mock data
- API integration with MSW

### E2E Tests (Playwright)
- Create new project flow
- Chat interaction flow
- Version revert flow
- Settings update flow

---

**Document Version:** 1.0
**Last Updated:** 2025-01-31
**Status:** Ready for implementation
