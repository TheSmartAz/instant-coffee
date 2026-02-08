# Phase B5: Data Protocol Generation

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B1 (Skills Registry), B2 (Orchestrator Routing)
  - **Blocks**: O1

## Goal

Generate shared data store scripts and state contracts that enable cross-page data sharing using localStorage, with event-driven updates and preview integration.

## Detailed Tasks

### Task 1: Generate State Contract

**Description**: Generate state contract JSON defining shared data structure.

**Implementation Details**:
- [ ] Create `StateContractGenerator` class
- [ ] Load contract template from skill (if available)
- [ ] Generate contract from LLM if template missing
- [ ] Include: shared_state_key, records_key, events_key, schema
- [ ] Validate contract structure

**Files to modify/create**:
- `packages/backend/app/services/data_protocol.py` (new file)
- `packages/backend/app/utils/product_doc.py` (new file)

**Acceptance Criteria**:
- [ ] Flow apps generate state contract
- [ ] Static apps have empty/minimal contract
- [ ] Contract includes event definitions
- [ ] Contract output to `<output_dir>/shared/state-contract.json`

### Task 2: Generate Data Store Script

**Description**: Generate `data-store.js` with state management and localStorage integration.

**Implementation Details**:
- [ ] Create script template with state management class
- [ ] Implement get/set/persist methods
- [ ] Add storage event listener for cross-tab sync
- [ ] Add event logging system
- [ ] Include debounced preview notification

**Files to modify/create**:
- `packages/backend/app/utils/product_doc.py`

**Acceptance Criteria**:
- [ ] Script outputs to `<output_dir>/shared/data-store.js`
- [ ] Implements InstantCoffeeDataStore class
- [ ] Supports get_state, set_state, persist
- [ ] Listens to storage events for cross-page sync
- [ ] Logs events to instant-coffee:events key

### Task 3: Generate Data Client Script

**Description**: Generate `data-client.js` with page-level data interaction helpers.

**Implementation Details**:
- [ ] Create client template with helper functions
- [ ] Implement cart helpers (add, update, remove)
- [ ] Implement booking helpers (draft, submit)
- [ ] Implement form helpers (draft, submit)
- [ ] Auto-inject into generated pages

**Files to modify/create**:
- `packages/backend/app/utils/product_doc.py`

**Acceptance Criteria**:
- [ ] Script outputs to `<output_dir>/shared/data-client.js`
- [ ] Provides product-type-specific helpers
- [ ] Helpers emit events on state changes
- [ ] Submitted data writes to records key
- [ ] Generated pages include script tags

### Task 4: Implement Preview Message Protocol

**Description**: Add postMessage protocol for iframe to parent communication.

**Implementation Details**:
- [ ] Define message format: {type, state, events, records}
- [ ] Add message broadcasting in data-store.js
- [ ] Debounce state update messages (300-500ms)
- [ ] Immediate message for submit events
- [ ] Include timestamp in messages

**Files to modify/create**:
- `packages/backend/app/utils/product_doc.py`

**Acceptance Criteria**:
- [ ] Messages sent on state changes (debounced)
- [ ] Messages sent immediately on submit events
- [ ] Message format includes type, data, timestamp
- [ ] Messages target window.parent

### Task 5: Integrate with Page Generation

**Description**: Ensure generated pages include data scripts and proper initialization.

**Implementation Details**:
- [ ] Inject data-store.js and data-client.js script tags
- [ ] Initialize data store on page load
- [ ] Restore state from localStorage on load
- [ ] Subscribe to storage events for cross-page sync
- [ ] Enable preview communication

**Files to modify/create**:
- `packages/backend/app/agents/generation.py` (update)

**Acceptance Criteria**:
- [ ] All Flow App pages include both scripts
- [ ] Static pages include data-store.js only
- [ ] Scripts loaded before custom page scripts
- [ ] State restored on page load
- [ ] Cross-page navigation preserves state

## Technical Specifications

### State Contract Schema

```json
{
  "shared_state_key": "instant-coffee:state",
  "records_key": "instant-coffee:records",
  "events_key": "instant-coffee:events",
  "schema": {
    "cart": {
      "items": [],
      "totals": {"subtotal": 0, "tax": 0, "total": 0},
      "currency": "USD"
    },
    "booking": {
      "draft": {}
    },
    "forms": {
      "draft": {}
    },
    "user": {
      "profile": {}
    }
  },
  "events": [
    "add_to_cart",
    "update_qty",
    "remove_item",
    "checkout_draft",
    "submit_booking",
    "submit_form",
    "clear_cart"
  ]
}
```

### data-store.js Template

```javascript
class InstantCoffeeDataStore {
  constructor(contract) {
    this.stateKey = contract.shared_state_key;
    this.recordsKey = contract.records_key;
    this.eventsKey = contract.events_key;
    this.state = this.loadState();
    this.records = this.loadRecords();
    this.events = [];

    // Listen for cross-page updates
    window.addEventListener('storage', (e) => {
      if (e.key === this.stateKey || e.key === this.recordsKey) {
        this.refresh();
      }
    });
  }

  loadState() {
    const data = localStorage.getItem(this.stateKey);
    return data ? JSON.parse(data) : this.getDefaultState();
  }

  loadRecords() {
    const data = localStorage.getItem(this.recordsKey);
    return data ? JSON.parse(data) : [];
  }

  getState() {
    return this.state;
  }

  setState(path, value) {
    // Update state
    this.state[path] = value;
    this.persistState();
    this.logEvent('state_update', { path });
    this.notifyPreview();
  }

  persistState() {
    localStorage.setItem(this.stateKey, JSON.stringify(this.state));
  }

  addRecord(type, payload) {
    const record = {
      type,
      payload,
      created_at: new Date().toISOString()
    };
    this.records.push(record);
    localStorage.setItem(this.recordsKey, JSON.stringify(this.records));
    this.notifyPreview(true); // Immediate
  }

  logEvent(name, data) {
    this.events.push({ name, data, timestamp: Date.now() });
    localStorage.setItem(this.eventsKey, JSON.stringify(this.events));
  }

  notifyPreview(immediate = false) {
    const message = {
      type: 'instant-coffee:update',
      state: this.state,
      events: this.events,
      records: this.records,
      timestamp: Date.now()
    };

    if (immediate || !this.debounceTimer) {
      window.parent.postMessage(message, '*');
      this.debounceTimer = setTimeout(() => {
        this.debounceTimer = null;
      }, immediate ? 0 : 300);
    }
  }

  refresh() {
    this.state = this.loadState();
    this.records = this.loadRecords();
  }
}
```

### Preview Message Protocol

```javascript
// Message sent from iframe to parent
{
  type: 'instant-coffee:update',
  state: { /* current state */ },
  events: [ /* event log */ ],
  records: [ /* submitted records */ ],
  timestamp: 1234567890
}

// Parent (Data Tab) listens:
window.addEventListener('message', (event) => {
  if (event.data.type === 'instant-coffee:update') {
    updateDataTab(event.data);
  }
});
```

### Service Interface

```python
class DataProtocolGenerator:
    def generate_state_contract(
        self,
        product_type: str,
        skill: SkillManifest
    ) -> dict:
        """Generate state contract JSON."""

    def generate_data_store_script(
        self,
        contract: dict
    ) -> str:
        """Generate data-store.js content."""

    def generate_data_client_script(
        self,
        product_type: str,
        contract: dict
    ) -> str:
        """Generate data-client.js content."""

    def inject_scripts_into_page(
        self,
        html: str,
        product_type: str
    ) -> str:
        """Inject script tags into generated HTML."""
```

## Testing Requirements

- [ ] Unit tests for state contract generation
- [ ] Unit tests for script generation
- [ ] Integration tests for localStorage persistence
- [ ] Tests for cross-page state sync
- [ ] Tests for preview message protocol
- [ ] Tests for event debouncing

## Notes & Warnings

- localStorage is synchronous - large states may block
- Consider size limits (typically 5-10MB)
- Records array should be pruned if too large
- Storage events only fire in other tabs/windows, not same page
- Preview messages use '*' for target - consider specific origin in production
- Debouncing is critical to avoid message flooding
- State must be serializable (no functions, circular refs)
