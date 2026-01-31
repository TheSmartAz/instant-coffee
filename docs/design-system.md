# Instant Coffee Design System v1.0

## Overview

This document defines the visual language and component specifications for the Instant Coffee web application. The app is desktop-first, uses React with shadcn/ui components, and follows a modern minimal aesthetic.

## Design Tokens

### Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--primary` | `#18181B` | Primary buttons, key text |
| `--accent` | `#3B82F6` | Links, active states, highlights |
| `--background` | `#FFFFFF` | Page background |
| `--foreground` | `#09090B` | Primary text |
| `--muted` | `#F4F4F5` | Secondary backgrounds, alternating rows |
| `--muted-foreground` | `#71717A` | Secondary text, timestamps |
| `--border` | `#E4E4E7` | Borders, dividers |

### Typography

| Token | Value |
|-------|-------|
| Font Family | `Inter, sans-serif` |
| Scale | `12 / 14 / 16 / 18 / 20 / 24 / 30 / 36px` |

### Spacing

| Token | Value |
|-------|-------|
| Base Unit | `4px` |
| Scale | `4 / 8 / 12 / 16 / 20 / 24 / 32 / 40 / 48 / 64px` |

### Borders & Shadows

| Token | Value |
|-------|-------|
| Border Radius | `8px` |
| Shadow | `0 1px 3px rgba(0,0,0,0.1)` |

## Component Styles

### Buttons

| Type | Style |
|------|-------|
| Primary | Solid `--primary` bg, white text |
| Secondary | Outline `--border`, `--foreground` text |
| Ghost | No border, hover shows `--muted` bg |

### Cards (Project Cards)

- Mini phone frame thumbnail
- `8px` border radius
- Subtle shadow on hover
- Project name + timestamp below

### Chat Messages

- Full-width, alternating `--background` / `--muted`
- Avatar (32px) on left
- Message content with proper spacing

### Phone Preview

- Realistic iPhone frame with notch
- 9:19.5 aspect ratio
- Content in iframe
- Centered in preview panel

### Version Timeline

- Vertical line with dots
- Current version: filled dot + accent color
- Past versions: outline dot
- Timestamp in `--muted-foreground`

## Page Layouts

### Homepage (Hero + Grid)

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
│  │   │ │   │ │   │ │   │               │
│  └───┘ └───┘ └───┘ └───┘               │
│  Name   Name   Name   Name              │
└─────────────────────────────────────────┘
```

**Key Elements:**
- Centered hero section with chat input
- Project gallery below in responsive grid
- Mini phone frame thumbnails for each project

### Project Page (3-Column Resizable)

```
┌─────────────────────────────────────────────────────────┐
│  ← Back    Project Name                     [⚙ Settings]│
├─────────────║───────────────────║───────────────────────┤
│             ║                   ║  Versions             │
│  Chat       ║   Preview         ║  ─────────────────── │
│  ═══════    ║   ┌───────────┐   ║  ● v3 (current)      │
│  [🤖] AI    ║   │  ┌─────┐  │   ║  │  10 min ago       │
│  message    ║   │  │     │  │   ║  │                   │
│             ║   │  │     │  │   ║  ○ v2                │
│  [👤] You   ║   │  │     │  │   ║  │  1 hour ago       │
│  message    ║   │  └─────┘  │   ║  │                   │
│             ║   └───────────┘   ║  ○ v1                │
│  ─────────  ║                   ║     2 hours ago      │
│  [Type...] [Send]              ║                      │
│             ║                   ║  [◀ Collapse]        │
└─────────────║───────────────────║───────────────────────┘
   resizable      resizable          collapsible
```

**Panel Specifications:**
- **Chat Panel**: Resizable, min-width 320px, default 360px
- **Preview Panel**: Resizable, flex-1 (takes remaining space)
- **Version Panel**: Collapsible, expanded 280px, collapsed 48px

### Settings Page (Sidebar Sections)

```
┌──────────┬──────────────────────────────────┐
│          │                                  │
│ Account  │  Model Configuration             │
│ Model ●  │  ────────────────────────────── │
│ Prefs    │                                  │
│          │  Default Model                   │
│          │  ┌────────────────────────┐     │
│          │  │ Claude Sonnet 4      ▼ │     │
│          │  └────────────────────────┘     │
│          │                                  │
│          │  Temperature                     │
│          │  [0.7 ─────●─────────────]      │
│          │                                  │
└──────────┴──────────────────────────────────┘
```

**Sections:**
- Account: User profile, API key management
- Model: Default model selection, temperature, max tokens
- Preferences: Output directory, auto-save settings

## shadcn/ui Components

### Required Components

| Component | Usage |
|-----------|-------|
| `resizable` | Chat/Preview panel layout |
| `collapsible` | Version panel toggle |
| `button` | All buttons (primary, secondary, ghost) |
| `input` | Text inputs, chat input |
| `card` | Project cards, settings sections |
| `avatar` | Chat message avatars |
| `scroll-area` | Chat messages, version list |
| `select` | Model selection dropdown |
| `slider` | Temperature setting |
| `separator` | Dividers |
| `tooltip` | Icon button hints |

### Custom Components (Build on top of shadcn)

| Component | Description |
|-----------|-------------|
| `PhoneFrame` | iPhone-style device frame for preview |
| `ProjectCard` | Mini phone frame + project metadata |
| `ChatMessage` | Full-width message with avatar |
| `VersionTimeline` | Vertical timeline with version dots |
| `ChatInput` | Text area with send button |

## Technical Notes

### CSS Variables Setup (Tailwind)

```css
@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 240 10% 3.9%;
    --muted: 240 4.8% 95.9%;
    --muted-foreground: 240 3.8% 46.1%;
    --border: 240 5.9% 90%;
    --primary: 240 5.9% 10%;
    --primary-foreground: 0 0% 98%;
    --accent: 217 91% 60%;
    --accent-foreground: 0 0% 98%;
    --radius: 0.5rem;
  }
}
```

### Font Setup

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

body {
  font-family: 'Inter', sans-serif;
}
```

### Responsive Breakpoints

| Breakpoint | Width | Usage |
|------------|-------|-------|
| `sm` | 640px | - |
| `md` | 768px | - |
| `lg` | 1024px | Minimum supported width |
| `xl` | 1280px | Optimal experience |
| `2xl` | 1536px | Large displays |

**Note:** This is a desktop-first application. Minimum supported viewport is 1024px.

---

**Version:** 1.0
**Last Updated:** 2025-01-31
