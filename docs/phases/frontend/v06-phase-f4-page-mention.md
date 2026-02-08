# Phase F4: Page Mention Component

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F2 (Image Upload & @Page Support)
  - **Blocks**: None

## Goal

Create a polished PageMentionPopover component with keyboard navigation, search filtering, and proper positioning for @Page autocomplete in ChatInput.

## Detailed Tasks

### Task 1: Create Component Structure

**Description**: Build the base PageMentionPopover component with list rendering.

**Implementation Details**:
- [ ] Create `PageMentionPopover.tsx` component
- [ ] Accept pages list and query string props
- [ ] Filter pages by query
- [ ] Render page list with slug and optional title
- [ ] Handle empty state

**Files to modify/create**:
- `packages/web/src/components/custom/PageMentionPopover.tsx` (new file)

**Acceptance Criteria**:
- [ ] Component renders dropdown list
- [ ] Pages filtered by search query
- [ ] Empty state shows "No matching pages"
- [ ] Each item shows page slug and title

### Task 2: Add Keyboard Navigation

**Description**: Implement arrow key and Enter navigation for the popover.

**Implementation Details**:
- [ ] Track selected index state
- [ ] Handle ArrowDown (next item)
- [ ] Handle ArrowUp (previous item)
- [ ] Handle Enter (select item)
- [ ] Handle Escape (close popover)

**Files to modify/create**:
- `packages/web/src/components/custom/PageMentionPopover.tsx`

**Acceptance Criteria**:
- [ ] Arrow keys navigate through list
- [ ] Selection wraps at boundaries
- [ ] Enter selects highlighted item
- [ ] Escape closes popover without selection

### Task 3: Implement Positioning Logic

**Description**: Calculate and apply proper popover positioning relative to textarea.

**Implementation Details**:
- [ ] Calculate caret/textarea position
- [ ] Position popover below textarea
- [ ] Handle viewport edge cases
- [ ] Adjust if popover would overflow
- [ ] Add arrow pointing to caret

**Files to modify/create**:
- `packages/web/src/components/custom/PageMentionPopover.tsx`
- `packages/web/src/utils/positioning.ts` (new file, if needed)

**Acceptance Criteria**:
- [ ] Popover appears below textarea
- [ ] Doesn't overflow viewport
- [ ] Adjusts position if too close to bottom
- [ ] Arrow points to caret position

### Task 4: Add Click Selection

**Description**: Handle mouse clicks on page items.

**Implementation Details**:
- [ ] Add onClick handler to items
- [ ] Call onSelect with selected page
- [ ] Close popover after selection
- [ ] Prevent textarea focus loss issues

**Files to modify/create**:
- `packages/web/src/components/custom/PageMentionPopover.tsx`

**Acceptance Criteria**:
- [ ] Click selects page
- [ ] Popover closes after selection
- [ ] Textarea remains focused
- [ ] @Page inserted correctly

### Task 5: Add Visual States and Styling

**Description**: Style the popover with proper visual feedback.

**Implementation Details**:
- [ ] Style selected item (highlight)
- [ ] Style hover state
- [ ] Add smooth transitions
- [ ] Style empty state
- [ ] Add scrollbar for long lists

**Files to modify/create**:
- `packages/web/src/components/custom/PageMentionPopover.tsx`
- `packages/web/src/components/custom/PageMentionPopover.module.css` (new file)

**Acceptance Criteria**:
- [ ] Selected item visually distinct
- [ ] Hover state visible
- [ ] Smooth transitions
- [ ] Scrollbar appears when needed
- [ ] Design matches app theme

### Task 6: Integrate with ChatInput

**Description**: Connect popover to ChatInput component.

**Implementation Details**:
- [ ] Detect @ character in textarea
- [ ] Track query text after @
- [ ] Show/hide popover appropriately
- [ ] Insert selected @Page into text
- [ ] Handle edge cases (space after @, etc.)

**Files to modify/create**:
- `packages/web/src/components/custom/ChatInput.tsx` (update)

**Acceptance Criteria**:
- [ ] Popover appears on @
- [ ] Popover closes on space or when complete
- [ ] Selected page inserted at cursor
- [ ] Works with existing text

## Technical Specifications

### Component Props

```typescript
interface Page {
  id: string;
  slug: string;
  title?: string;
  role?: string;
}

interface PageMentionPopoverProps {
  pages: Page[];
  query: string;
  position: { x: number; y: number };
  onSelect: (page: Page) => void;
  onClose: () => void;
  maxHeight?: number;
}
```

### Component Implementation

```tsx
import React, { useState, useEffect, useCallback } from 'react';
import styles from './PageMentionPopover.module.css';

export function PageMentionPopover({
  pages,
  query,
  position,
  onSelect,
  onClose,
  maxHeight = 200
}: PageMentionPopoverProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Filter pages by query
  const filteredPages = pages.filter(page =>
    page.slug.toLowerCase().includes(query.toLowerCase()) ||
    (page.title && page.title.toLowerCase().includes(query.toLowerCase()))
  );

  // Reset selection when filtered pages change
  useEffect(() => {
    setSelectedIndex(0);
  }, [query, pages]);

  // Handle keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedIndex(i =>
          i < filteredPages.length - 1 ? i + 1 : i
        );
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedIndex(i => (i > 0 ? i - 1 : 0));
        break;
      case 'Enter':
        e.preventDefault();
        if (filteredPages[selectedIndex]) {
          onSelect(filteredPages[selectedIndex]);
        }
        break;
      case 'Escape':
        e.preventDefault();
        onClose();
        break;
    }
  }, [filteredPages, selectedIndex, onSelect, onClose]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Handle mouse selection
  const handleMouseEnter = (index: number) => {
    setSelectedIndex(index);
  };

  const handleClick = (page: Page) => {
    onSelect(page);
  };

  if (filteredPages.length === 0) {
    return (
      <div
        className={styles.popover}
        style={{ left: position.x, top: position.y }}
      >
        <div className={styles.empty}>No matching pages</div>
      </div>
    );
  }

  return (
    <div
      className={styles.popover}
      style={{ left: position.x, top: position.y }}
    >
      <ul
        className={styles.list}
        style={{ maxHeight: `${maxHeight}px` }}
      >
        {filteredPages.map((page, index) => (
          <li
            key={page.id}
            className={`${styles.item} ${index === selectedIndex ? styles.selected : ''}`}
            onMouseEnter={() => handleMouseEnter(index)}
            onClick={() => handleClick(page)}
          >
            <span className={styles.slug}>@{page.slug}</span>
            {page.title && (
              <span className={styles.title}>{page.title}</span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### CSS Module

```css
/* PageMentionPopover.module.css */
.popover {
  position: absolute;
  z-index: 1000;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  min-width: 200px;
  max-width: 300px;
}

.list {
  list-style: none;
  margin: 0;
  padding: 4px;
  overflow-y: auto;
}

.item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  border-radius: 4px;
  transition: background-color 0.15s ease;
}

.item:hover,
.item.selected {
  background-color: var(--bg-hover);
}

.slug {
  font-weight: 500;
  color: var(--text-primary);
}

.title {
  font-size: 0.85em;
  color: var(--text-secondary);
}

.empty {
  padding: 12px;
  text-align: center;
  color: var(--text-secondary);
  font-size: 0.9em;
}
```

### ChatInput Integration

```tsx
// In ChatInput.tsx
const [mentionState, setMentionState] = useState<{
  open: boolean;
  query: string;
  position: { x: number; y: number };
  startIndex: number;
} | null>(null);

const handleKeyDown = (e: React.KeyboardEvent) => {
  const textarea = e.target as HTMLTextAreaElement;

  // Trigger mention on @
  if (e.key === '@' && !mentionState?.open) {
    const rect = textarea.getBoundingClientRect();
    const cursorPosition = getCaretCoordinates(textarea, textarea.selectionEnd);
    setMentionState({
      open: true,
      query: '',
      position: {
        x: rect.left + cursorPosition.left,
        y: rect.bottom + 4
      },
      startIndex: textarea.selectionEnd
    });
  }

  // Close on space
  if (e.key === ' ' && mentionState?.open) {
    setMentionState(null);
  }
};

const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
  setText(e.target.value);

  // Update query if mention is open
  if (mentionState?.open) {
    const query = text.slice(mentionState.startIndex + 1, e.target.selectionEnd);
    if (!query.includes(' ')) {
      setMentionState(prev => prev ? { ...prev, query } : null);
    } else {
      setMentionState(null);
    }
  }
};

const handlePageSelect = (page: Page) => {
  if (!mentionState) return;

  const before = text.slice(0, mentionState.startIndex);
  const after = text.slice(mentionState.startIndex + 1 + mentionState.query.length);
  const newText = `${before}@${page.slug} ${after}`;

  setText(newText);
  setMentionState(null);

  // Focus back on textarea
  textareaRef.current?.focus();
};

return (
  <div className="chat-input-wrapper">
    <textarea
      ref={textareaRef}
      value={text}
      onChange={handleTextChange}
      onKeyDown={handleKeyDown}
    />

    {mentionState?.open && (
      <PageMentionPopover
        pages={pages}
        query={mentionState.query}
        position={mentionState.position}
        onSelect={handlePageSelect}
        onClose={() => setMentionState(null)}
      />
    )}
  </div>
);
```

## Testing Requirements

- [ ] Unit tests for PageMentionPopover component
- [ ] Tests for keyboard navigation
- [ ] Tests for filtering logic
- [ ] Tests for selection callback
- [ ] Integration tests with ChatInput
- [ ] Tests for edge cases (empty list, special characters)

## Notes & Warnings

- Caret position calculation requires a utility function (use existing libraries like textarea-caret)
- Popover should close if user clicks outside
- Position calculation needs to account for scroll position
- Consider adding a "Create new page" option if no matches
- @ mentions should be case-insensitive for matching but preserve entered case
- Popover should handle very long page titles (truncate with ellipsis)
- Ensure accessibility (ARIA attributes, keyboard support)
