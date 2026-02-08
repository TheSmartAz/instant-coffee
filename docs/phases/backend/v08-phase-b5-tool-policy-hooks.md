# Phase B5: Tool Policy Hooks

## Metadata

- **Category**: Backend
- **Priority**: P1
- **Estimated Complexity**: Medium
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: v08-B3 (Orchestration Run Integration)
  - **Blocks**: None

## Goal

Add pre/post tool-use policy hooks to BaseAgent's tool handler wrapper, implementing default policies for command whitelisting, path boundary enforcement, sensitive content detection, and large output truncation. Emit `tool_policy_blocked` and `tool_policy_warn` events.

## Detailed Tasks

### Task 1: Create Tool Policy Service

**Description**: Implement the policy evaluation engine.

**Implementation Details**:
- [x] Create `packages/backend/app/services/tool_policy.py`
- [x] Implement `ToolPolicyService` class with:
  - `pre_tool_use(policy_context)` — evaluate before tool execution
  - `post_tool_use(policy_context, result)` — evaluate after tool execution
- [x] Policy context includes: tool name, arguments, session_id, run_id
- [x] Return `PolicyResult` with: `action` (allow/warn/block), `reason`, `details`

**Files to modify/create**:
- `packages/backend/app/services/tool_policy.py`

**Acceptance Criteria**:
- [x] Pre and post hooks evaluate correctly
- [x] PolicyResult returned with clear action/reason

---

### Task 2: Implement Default Policies

**Description**: Implement the 4 default policies from spec section 10.2.

**Implementation Details**:
- [x] **Command whitelist**: For shell-type tools, only allow commands matching `tool_policy_allowed_cmd_prefixes`
- [x] **Path boundary**: Reject file operations outside project directory
- [x] **Sensitive content detection**: Scan for token/key/secret patterns in tool arguments and results
- [x] **Large output truncation**: Truncate tool results exceeding size threshold, log audit summary

**Files to modify/create**:
- `packages/backend/app/services/tool_policy.py`

**Acceptance Criteria**:
- [x] Command whitelist blocks non-whitelisted commands
- [x] Path boundary rejects out-of-project paths
- [x] Sensitive patterns detected (API keys, tokens, secrets)
- [x] Large outputs truncated with summary

---

### Task 3: Integrate Hooks into BaseAgent

**Description**: Wire policy hooks into the tool handler wrapper in BaseAgent.

**Implementation Details**:
- [x] Modify `packages/backend/app/agents/base.py`
- [x] In `_wrap_tool_handler()`, insert `pre_tool_use()` before execution
- [x] Insert `post_tool_use()` after execution
- [x] Respect policy mode: `off` (skip), `log_only` (warn only), `enforce` (block on high risk)
- [x] On block: emit `tool_policy_blocked` event, return error to agent
- [x] On warn: emit `tool_policy_warn` event, continue execution

**Files to modify/create**:
- `packages/backend/app/agents/base.py`

**Acceptance Criteria**:
- [x] Hooks execute for every tool call
- [x] `off` mode skips all checks
- [x] `log_only` mode emits warnings but doesn't block
- [x] `enforce` mode blocks high-risk calls
- [x] Events emitted with run_id context

---

### Task 4: Configuration

**Description**: Add tool policy configuration options.

**Implementation Details**:
- [x] Add to `packages/backend/app/config.py`:
  - `tool_policy_enabled: bool = True`
  - `tool_policy_mode: str = "log_only"` (off/log_only/enforce)
  - `tool_policy_allowed_cmd_prefixes: list[str] = [...]`
- [x] Support environment variable overrides

**Files to modify/create**:
- `packages/backend/app/config.py`

**Acceptance Criteria**:
- [x] All 3 config options available
- [x] Defaults match spec (enabled, log_only mode)
- [x] Environment variable overrides work

## Technical Specifications

### Policy Modes

| Mode | Behavior |
|------|----------|
| `off` | No policy evaluation |
| `log_only` | Evaluate, emit warn events, never block (default) |
| `enforce` | Evaluate, block high-risk, emit blocked/warn events |

### Policy Events

```json
{
  "type": "tool_policy_blocked",
  "run_id": "...",
  "payload": {
    "tool": "shell",
    "policy": "command_whitelist",
    "reason": "Command 'rm -rf /' not in allowed prefixes",
    "arguments": {...}
  }
}
```

### Default Allowed Command Prefixes

```python
["npm", "npx", "node", "python", "pip", "git", "ls", "cat", "echo", "mkdir", "cp"]
```

## Testing Requirements

- [x] Unit test: command whitelist blocks/allows correctly
- [x] Unit test: path boundary detection
- [x] Unit test: sensitive content pattern matching
- [x] Unit test: large output truncation
- [x] Unit test: policy mode switching (off/log_only/enforce)
- [x] Unit test: events emitted correctly
- [x] Integration test: tool call blocked in enforce mode
- [x] Integration test: tool call warned in log_only mode

## Notes & Warnings

- Do NOT modify business tool implementations — hooks wrap externally
- Start with `log_only` mode to avoid breaking existing workflows
- Sensitive content patterns should be configurable for future extension
- Large output threshold should be configurable (default ~100KB)
