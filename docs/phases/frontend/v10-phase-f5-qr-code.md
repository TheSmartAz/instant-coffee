# Phase v10-F5: QR Code Sharing

## Metadata

- **Category**: Frontend
- **Priority**: P1
- **Estimated Complexity**: Low
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v10-F4 (Deploy Button - needs URL)
  - **Blocks**: None (enhancement)

## Goal

Add QR code generation for easy mobile sharing of deployed pages.

## Detailed Tasks

### Task 1: Install QR library

**Description**: Add qrcode library.

**Implementation Details**:
- [ ] Run `npm install qrcode`
- [ ] Verify installation

**Files to modify**:
- `packages/web/package.json`

**Acceptance Criteria**:
- [ ] Library installed

---

### Task 2: Add QR button to Deploy UI

**Description**: Add QR code generation after deployment.

**Implementation Details**:
- [ ] Add "Show QR" button after successful deploy
- [ ] Generate QR code from deploy URL
- [ ] Display in modal or popover

**Files to modify**:
- `packages/web/src/components/custom/WorkbenchPanel.tsx`

**Acceptance Criteria**:
- [ ] QR code generated

## Technical Specifications

### Implementation

```typescript
import QRCode from 'qrcode';

const generateQR = async (url: string) => {
  return await QRCode.toDataURL(url, {
    width: 256,
    margin: 2
  });
};
```

### UI

```
┌─────────────────────────────────┐
│  Deploy Success!               │
│  https://xxx.netlify.app       │
│  ┌───────────┐                  │
│  │   QR      │  [Copy URL]      │
│  │   CODE    │  [Download QR]   │
│  └───────────┘                  │
└─────────────────────────────────┘
```

## Testing Requirements

- [ ] Test QR generation
- [ ] Test scanability

## Notes & Warning

- Use lightweight QR library
- Consider qrcode.react for React integration
