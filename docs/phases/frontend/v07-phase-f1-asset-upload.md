# Phase F1: Asset Upload UI

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can start immediately
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: None (but needed for full workflow)

## Goal

Implement asset upload functionality in ChatInput component with support for Logo, Style Reference, Background, and Product Image types.

## Detailed Tasks

### Task 1: Update ChatInput Component

**Description**: Add asset upload button and file handling to ChatInput

**Implementation Details**:
- [ ] Modify `packages/web/src/components/custom/ChatInput.tsx`
- [ ] Add upload button/icon next to send button
- [ ] Implement file selection modal/popover
- [ ] Add asset type selector (dropdown)
- [ ] Show upload progress indicator

**Files to modify**:
- `packages/web/src/components/custom/ChatInput.tsx`

**Acceptance Criteria**:
- [ ] Upload button visible in chat input
- [ ] File picker opens on click
- [ ] Asset type can be selected
- [ ] Progress shown during upload

---

### Task 2: Implement Upload API Integration

**Description**: Connect frontend to asset upload API endpoint

**Implementation Details**:
- [ ] Create/update `packages/web/src/api/assets.ts`
- [ ] Implement uploadAsset(file, assetType) function
- [ ] Handle multipart/form-data request
- [ ] Process API response (AssetRef)
- [ ] Update chat message with asset reference

**Files to create/modify**:
- `packages/web/src/api/assets.ts` (new)
- `packages/web/src/api/client.ts` (update)

**Acceptance Criteria**:
- [ ] POST /sessions/{session_id}/assets works
- [ ] Response includes asset ID and URL
- [ ] Error handling for invalid files
- [ ] File size limit enforced

---

### Task 3: Create Asset Type Selector UI

**Description**: Build UI for selecting asset type before upload

**Implementation Details**:
- [ ] Create `packages/web/src/components/custom/AssetTypeSelector.tsx`
- [ ] Define asset types: Logo, Style Reference, Background, Product Image
- [ ] Add icons for each type
- [ ] Show descriptions for each type
- [ ] Handle selection state

**Files to create**:
- `packages/web/src/components/custom/AssetTypeSelector.tsx`

**Acceptance Criteria**:
- [ ] All 4 asset types shown
- [ ] Icons and labels clear
- [ ] Selection persists for current upload
- [ ] Cancel option available

---

### Task 4: Display Uploaded Assets in Chat

**Description**: Show uploaded asset thumbnails in chat messages

**Implementation Details**:
- [ ] Update `packages/web/src/components/custom/ChatPanel.tsx`
- [ ] Parse asset references in messages
- [ ] Render asset thumbnails
- [ ] Add download/view options
- [ ] Show asset type badge

**Files to modify**:
- `packages/web/src/components/custom/ChatPanel.tsx`

**Acceptance Criteria**:
- [ ] Asset thumbnails render in chat
- [ ] Asset type badge visible
- [ ] Click opens full image view
- [ ] Multiple assets in one message supported

---

### Task 5: Add Asset to Chat State

**Description**: Track uploaded assets in chat context/state

**Implementation Details**:
- [ ] Update `packages/web/src/hooks/useChat.ts`
- [ ] Add assets array to chat state
- [ ] Implement addAsset(assetRef) function
- [ ] Implement getAssetById(id) function
- [ ] Persist assets in localStorage

**Files to modify**:
- `packages/web/src/hooks/useChat.ts`

**Acceptance Criteria**:
- [ ] Assets tracked per session
- [ ] Asset list survives page refresh
- [ ] Assets included in chat context
- [ ] Asset removal supported

## Technical Specifications

### Asset Upload API

```typescript
// api/assets.ts
export interface AssetRef {
  id: string;       // "asset:logo_abc123"
  url: string;      // "/assets/{sessionId}/logo_abc123.png"
  type: string;    // "image/png" | "image/jpeg" | "image/webp"
  width?: number;
  height?: number;
}

export type AssetType = 'logo' | 'style_ref' | 'background' | 'product_image';

export async function uploadAsset(
  file: File,
  assetType: AssetType
): Promise<AssetRef> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await client.post(
    `/sessions/${sessionId}/assets`,
    formData,
    {
      params: { asset_type: assetType },
      headers: { 'Content-Type': 'multipart/form-data' }
    }
  );

  return response.data;
}
```

### Asset Type Selector Component

```typescript
interface AssetTypeSelectorProps {
  selected: AssetType | null;
  onSelect: (type: AssetType) => void;
  onCancel: () => void;
}

const ASSET_TYPES: { type: AssetType; label: string; icon: string; description: string }[] = [
  { type: 'logo', label: 'Logo', icon: '🔷', description: '导航栏和页脚显示' },
  { type: 'style_ref', label: '风格参考', icon: '🎨', description: '提取视觉风格' },
  { type: 'background', label: '背景图', icon: '🖼️', description: '首屏或分区背景' },
  { type: 'product_image', label: '产品图', icon: '📦', description: '商品或内容展示' }
];
```

### ChatInput Integration

```typescript
// ChatInput.tsx
interface ChatInputProps {
  // ... existing props
  onAssetUpload?: (file: File, type: AssetType) => void;
}

function ChatInput({ onAssetUpload }: ChatInputProps) {
  const [showAssetPicker, setShowAssetPicker] = useState(false);

  return (
    <div className="chat-input-container">
      <textarea {...} />
      <button onClick={() => setShowAssetPicker(true)}>
        <Icon name="upload" />
      </button>
      {showAssetPicker && (
        <AssetTypeSelector
          onSelect={(type) => {
            // Trigger file input
          }}
          onCancel={() => setShowAssetPicker(false)}
        />
      )}
      <button className="send-button">...</button>
    </div>
  );
}
```

## Testing Requirements

- [ ] Unit test: AssetTypeSelector renders correctly
- [ ] Unit test: Upload API returns correct response
- [ ] Integration test: Full upload flow
- [ ] Test with different file types
- [ ] Test file size limits

## Notes & Warnings

- File size limit: 10MB per file
- Supported formats: PNG, JPEG, WebP, SVG
- Asset IDs are session-scoped
- Consider adding drag-and-drop support later
