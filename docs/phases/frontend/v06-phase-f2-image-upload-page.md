# Phase F2: Image Upload & @Page Support

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: F4

## Goal

Enable image upload via drag-and-drop in ChatInput, add @Page mention autocomplete dropdown, and send both to the backend.

## Detailed Tasks

### Task 1: Add Image Upload to ChatInput

**Description**: Modify ChatInput to accept image uploads.

**Implementation Details**:
- [ ] Add file input (hidden) triggered by button
- [ ] Support drag-and-drop on textarea
- [ ] Preview uploaded images before sending
- [ ] Limit to 3 images max
- [ ] Convert images to base64 for sending

**Files to modify/create**:
- `packages/web/src/components/custom/ChatInput.tsx` (update)

**Acceptance Criteria**:
- [ ] Image button opens file picker
- [ ] Drag-and-drop works on textarea
- [ ] Images display as thumbnails
- [ ] Remove button on each image thumbnail
- [ ] Max 3 images enforced

### Task 2: Create Image Preview Component

**Description**: Build component to display image thumbnails with remove button.

**Implementation Details**:
- [ ] Create `ImageThumbnail` component
- [ ] Show image preview
- [ ] Add remove (X) button
- [ ] Show file size and dimensions
- [ ] Display in horizontal scrollable list

**Files to modify/create**:
- `packages/web/src/components/custom/ImageThumbnail.tsx` (new file)

**Acceptance Criteria**:
- [ ] Thumbnail renders image
- [ ] Remove button visible on hover
- [ ] File info shown on hover
- [ ] Multiple thumbnails scroll horizontally

### Task 3: Add @Page Autocomplete Dropdown

**Description**: Create dropdown that shows page options when typing @.

**Implementation Details**:
- [ ] Create `PageMentionPopover` component
- [ ] Trigger on @ character in textarea
- [ ] Filter pages by search text
- [ ] Show page slug and title
- [ ] Insert @Page into textarea on selection

**Files to modify/create**:
- `packages/web/src/components/custom/PageMentionPopover.tsx` (new file)

**Acceptance Criteria**:
- [ ] Dropdown appears after @
- [ ] Pages filtered as user types
- [ ] Keyboard navigation (arrow keys, enter)
- [ ] Click to select
- [ ] @Page inserted at cursor position

### Task 4: Parse @Page from Message

**Description**: Extract @Page mentions before sending to backend.

**Implementation Details**:
- [ ] Parse message for @Page pattern
- [ ] Extract page names
- [ ] Include in request metadata
- [ ] Handle multiple @Page mentions

**Files to modify/create**:
- `packages/web/src/utils/chat.ts` (new file)

**Acceptance Criteria**:
- [ ] Finds all @Page mentions
- [ ] Returns list of page slugs
- [ ] Case-insensitive matching

### Task 5: Update Chat API Client

**Description**: Send images and @Page data to backend.

**Implementation Details**:
- [ ] Update chat request type
- [ ] Include images array (base64)
- [ ] Include target_pages array
- [ ] Include style_reference mode

**Files to modify/create**:
- `packages/web/src/api/client.ts` (update)
- `packages/web/src/types/index.ts` (update)

**Acceptance Criteria**:
- [ ] Request includes images if present
- [ ] Request includes parsed @Page mentions
- [ ] Backend accepts the request

### Task 6: Add Image Validation

**Description**: Validate uploaded images before sending.

**Implementation Details**:
- [ ] Check file type (image/*)
- [ ] Check file size (max 5MB)
- [ ] Check dimensions (optional)
- [ ] Show error for invalid files

**Files to modify/create**:
- `packages/web/src/components/custom/ChatInput.tsx`

**Acceptance Criteria**:
- [ ] Only images accepted
- [ ] Files > 5MB rejected with message
- [ ] Non-image files rejected
- [ ] Error message clear to user

## Technical Specifications

### ChatInput Component Updates

```tsx
interface ChatInputProps {
  onSend: (message: string, attachments: Attachment[]) => void;
  pages?: Page[];  // For @Page autocomplete
}

interface Attachment {
  type: 'image';
  data: string;  // base64
  name: string;
  size: number;
}

export function ChatInput({ onSend, pages = [] }: ChatInputProps) {
  const [text, setText] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');

  const handleFileSelect = (files: FileList) => {
    // Validate and convert to base64
    // Add to attachments (max 3)
  };

  const handleDrop = (e: DragEvent) => {
    // Handle drop on textarea
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    // Trigger autocomplete on @
  };

  return (
    <div className="chat-input-container">
      {/* Image preview area */}
      {attachments.length > 0 && (
        <div className="image-previews">
          {attachments.map((att, i) => (
            <ImageThumbnail
              key={i}
              attachment={att}
              onRemove={() => setAttachments(atts => atts.filter((_, j) => j !== i))}
            />
          ))}
        </div>
      )}

      {/* Textarea with autocomplete */}
      <div className="input-wrapper">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onDrop={handleDrop}
          placeholder="Describe your changes... Use @Page to target specific pages"
        />

        {/* Autocomplete popover */}
        {mentionOpen && (
          <PageMentionPopover
            pages={pages}
            query={mentionQuery}
            onSelect={(page) => insertMention(page)}
          />
        )}
      </div>

      {/* Action buttons */}
      <div className="input-actions">
        <button onClick={() => fileInputRef.current?.click()}>
          <ImageIcon />
        </button>
        <button onClick={() => onSend(text, attachments)}>
          <SendIcon />
        </button>
      </div>
    </div>
  );
}
```

### PageMentionPopover Component

```tsx
interface PageMentionPopoverProps {
  pages: Page[];
  query: string;
  onSelect: (page: Page) => void;
  position: { x: number; y: number };
}

export function PageMentionPopover({ pages, query, onSelect, position }: PageMentionPopoverProps) {
  const filteredPages = pages.filter(p =>
    p.slug.toLowerCase().includes(query.toLowerCase()) ||
    p.title?.toLowerCase().includes(query.toLowerCase())
  );

  const [selectedIndex, setSelectedIndex] = useState(0);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        setSelectedIndex(i => Math.min(i + 1, filteredPages.length - 1));
      } else if (e.key === 'ArrowUp') {
        setSelectedIndex(i => Math.max(i - 1, 0));
      } else if (e.key === 'Enter' && filteredPages[selectedIndex]) {
        onSelect(filteredPages[selectedIndex]);
      }
    };
    // ... setup and cleanup
  }, [filteredPages, selectedIndex]);

  return (
    <div className="mention-popover" style={{ left: position.x, top: position.y }}>
      {filteredPages.length === 0 ? (
        <div className="no-results">No matching pages</div>
      ) : (
        <ul>
          {filteredPages.map((page, i) => (
            <li
              key={page.id}
              className={i === selectedIndex ? 'selected' : ''}
              onClick={() => onSelect(page)}
            >
              <span className="page-slug">@{page.slug}</span>
              {page.title && <span className="page-title">{page.title}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

### Chat Request Type

```typescript
interface ChatRequest {
  session_id: string;
  message: {
    role: 'user';
    content: string;
    images?: string[];  // base64 encoded
    target_pages?: string[];  // Parsed from @Page mentions
  };
  style_reference?: {
    mode: 'full_mimic' | 'style_only';
    scope_pages?: string[];
  };
}

// Page mention parser
function parsePageMentions(message: string): string[] {
  const mentions = message.match(/@(\w+)/g);
  return mentions ? mentions.map(m => m.substring(1).toLowerCase()) : [];
}
```

## Testing Requirements

- [ ] Unit tests for ImageThumbnail component
- [ ] Tests for PageMentionPopover filtering
- [ ] Tests for page mention parser
- [ ] Integration tests for ChatInput with attachments
- [ ] Tests for image validation
- [ ] Drag-and-drop tests

## Notes & Warnings

- Base64 encoding increases payload size - consider resize for large images
- @Page autocomplete should match against existing pages in project
- Mention popover should not overflow viewport
- Image upload button should show clear visual indicator
- Consider adding loading state while images are being processed
- Handle case where user @ mentions a non-existent page (backend validation)
- Mention trigger should work after spaces but not in the middle of words
