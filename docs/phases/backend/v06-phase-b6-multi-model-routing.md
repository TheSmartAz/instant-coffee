# Phase B6: Multi-model Routing

## Metadata

- **Category**: Backend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: B2 (Orchestrator Routing), B3 (Style Reference)
  - **Blocks**: B7

## Goal

Implement multi-model routing with role-based model selection (classifier, writer, expander, validator, style_refiner), fallback logic, and OpenAI-compatible configuration.

## Detailed Tasks

### Task 1: Define Model Roles and Configuration

**Description**: Create configuration structure for model roles and pools.

**Implementation Details**:
- [ ] Define model role enums: classifier, writer, expander, validator, style_refiner
- [ ] Create model pool configuration structure
- [ ] Support per-product-type model preferences
- [ ] Add model configuration to config.py

**Files to modify/create**:
- `packages/backend/app/config.py` (update)
- `packages/backend/app/llm/model_catalog.py` (new file)

**Acceptance Criteria**:
- [ ] Model roles are well-defined enum
- [ ] Configuration supports multiple models per role
- [ ] Product-specific overrides are supported
- [ ] Configuration is environment-based

### Task 2: Implement Model Client Factory

**Description**: Create factory for instantiating OpenAI-compatible model clients.

**Implementation Details**:
- [ ] Create `ModelClientFactory` class
- [ ] Support model, base_url, api_key configuration
- [ ] Cache instantiated clients
- [ ] Handle client creation failures

**Files to modify/create**:
- `packages/backend/app/llm/client_factory.py` (new file)

**Acceptance Criteria**:
- [ ] Creates client from model config
- [ ] Supports custom base_url
- [ ] Caches clients by config hash
- [ ] Raises clear error on invalid config

### Task 3: Implement Model Pool Management

**Description**: Create service to manage model pools and fallback selection.

**Implementation Details**:
- [ ] Create `ModelPoolManager` class
- [ ] Implement get_model(role, product_type) method
- [ ] Support priority-ordered fallback lists
- [ ] Track model usage and failures
- [ ] Log all model selections

**Files to modify/create**:
- `packages/backend/app/llm/model_pool.py` (new file)

**Acceptance Criteria**:
- [ ] Returns first available model in pool
- [ ] Falls to next model on failure
- [ ] Logs model selection decisions
- [ ] Tracks failure counts per model

### Task 4: Implement Fallback Logic

**Description**: Add fallback triggering on specific failure conditions.

**Implementation Details**:
- [ ] Detect timeout and request failures
- [ ] Detect validator hard-fail signals
- [ ] Detect missing critical fields
- [ ] Implement retry with next model
- [ ] Limit fallback attempts

**Files to modify/create**:
- `packages/backend/app/llm/model_pool.py`

**Acceptance Criteria**:
- [ ] Fallback on timeout
- [ ] Fallback on connection error
- [ ] Fallback on validator hard-fail
- [ ] Fallback on missing required fields
- [ ] Max 3 fallback attempts

### Task 5: Update Agent Base Class for Model Routing

**Description**: Modify BaseAgent to use model pool instead of fixed model.

**Implementation Details**:
- [ ] Add role parameter to agent initialization
- [ ] Request model from pool for each call
- [ ] Pass product_type for model selection
- [ ] Handle fallback retries

**Files to modify/create**:
- `packages/backend/app/agents/base.py` (update)

**Acceptance Criteria**:
- [ ] Agents specify their role (classifier, writer, etc.)
- [ ] Model selected from pool based on role
- [ ] Fallback handled transparently
- [ ] Original exception re-raised if all models fail

### Task 6: Add Model Capability Detection

**Description**: Detect and expose model capabilities (vision, max tokens, etc.).

**Implementation Details**:
- [ ] Define model capability flags
- [ ] Detect vision support for style_refiner
- [ ] Detect max token limits
- [ ] Store capability metadata in catalog

**Files to modify/create**:
- `packages/backend/app/llm/model_catalog.py`

**Acceptance Criteria**:
- [ ] Vision capability detected/declared
- [ ] Token limits known per model
- [ ] Capability checked before use
- [ ] Graceful degradation when capability missing

### Task 7: Configure Model Pools by Product Type

**Description**: Set up default model pools for different product types.

**Implementation Details**:
- [ ] Configure default pools for all roles
- [ ] Configure landing-specific pools (aesthetic priority)
- [ ] Configure card-specific pools (aesthetic priority)
- [ ] Configure flow app pools (stability priority)
- [ ] Document model selection strategy

**Files to modify/create**:
- `packages/backend/app/config.py` (update)

**Acceptance Criteria**:
- [ ] Landing/card use faster model + strong style refiner
- [ ] Flow apps use stable model for writer
- [ ] Classifier uses light/fast model
- [ ] Validator uses most reliable model

## Technical Specifications

### Configuration Structure

```python
# config.py
MODEL_CLASSIFIER = "light-model-name"
MODEL_WRITER = "stable-model-name"
MODEL_EXPANDER = "mid-model-name"
MODEL_VALIDATOR = "stable-model-name"
MODEL_STYLE_REFINER = "aesthetic-model-name"

# Alternative: Pool-based configuration
MODEL_POOLS = {
    "classifier": ["light-1", "light-2"],
    "writer": {
        "default": ["stable-1", "stable-2"],
        "landing": ["fast-1", "stable-1"],
        "card": ["fast-1", "stable-1"],
        "ecommerce": ["stable-1", "stable-2"],
        "booking": ["stable-1", "stable-2"],
        "dashboard": ["stable-1", "stable-2"],
    },
    "expander": ["mid-1", "stable-1"],
    "validator": ["stable-1", "stable-2"],
    "style_refiner": {
        "default": ["aesthetic-1", "stable-1"],
        "landing": ["aesthetic-1", "aesthetic-2"],
        "card": ["aesthetic-1", "aesthetic-2"],
    }
}

MODEL_CATALOG = {
    "light-1": {
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "capabilities": ["text"],
        "max_tokens": 128000
    },
    "stable-1": {
        "model": "gpt-4o",
        "base_url": "https://api.openai.com/v1",
        "capabilities": ["text", "vision"],
        "max_tokens": 128000
    },
    # ... more models
}
```

### Model Pool Manager

```python
class ModelPoolManager:
    def __init__(self, config: dict, client_factory: ModelClientFactory):
        self.config = config
        self.factory = client_factory
        self.failures = defaultdict(int)

    def get_model(
        self,
        role: str,
        product_type: Optional[str] = None
    ) -> LLMClient:
        """Get available model for role, with fallback."""
        pools = self._get_pools_for_role(role, product_type)

        for model_id in pools:
            if self.failures[model_id] >= 3:
                continue  # Skip recently failed models

            try:
                return self._create_client(model_id)
            except Exception as e:
                self.failures[model_id] += 1
                logger.warning(f"Model {model_id} failed: {e}")

        raise ModelExhaustedError(f"No models available for role: {role}")

    def report_failure(self, model_id: str):
        """Report a model failure for fallback tracking."""
        self.failures[model_id] += 1

    def reset_failure_count(self, model_id: str):
        """Reset failure count after successful call."""
        self.failures[model_id] = 0
```

### Fallback Conditions

```python
class FallbackTrigger(Enum):
    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    VALIDATOR_HARD_FAIL = "validator_hard_fail"
    MISSING_FIELD = "missing_field"
    INVALID_STRUCTURE = "invalid_structure"

def should_fallback(
    error: Exception,
    response: Any,
    role: str
) -> Optional[FallbackTrigger]:
    """Determine if fallback should be triggered."""

    # Request-level failures
    if isinstance(error, TimeoutError):
        return FallbackTrigger.TIMEOUT
    if isinstance(error, ConnectionError):
        return FallbackTrigger.CONNECTION_ERROR

    # Response-level failures
    if response and hasattr(response, 'validator_result'):
        if response.validator_result.hard_fail:
            return FallbackTrigger.VALIDATOR_HARD_FAIL

    # Missing critical fields
    if response and role == "writer":
        if not response.state_contract and response.product_type in ["ecommerce", "booking"]:
            return FallbackTrigger.MISSING_FIELD

    return None
```

### Agent Integration

```python
# BaseAgent update
class BaseAgent:
    def __init__(
        self,
        role: AgentRole,  # e.g., AgentRole.WRITER
        product_type: Optional[str] = None,
        model_pool: Optional[ModelPoolManager] = None
    ):
        self.role = role
        self.product_type = product_type
        self.model_pool = model_pool

    async def call_llm(self, prompt: str, **kwargs) -> str:
        """Call LLM with automatic fallback."""
        if self.model_pool:
            client = self.model_pool.get_model(
                self.role.value,
                self.product_type
            )
        else:
            client = self.default_client

        return await client.generate(prompt, **kwargs)
```

## Testing Requirements

- [ ] Unit tests for model pool selection
- [ ] Unit tests for fallback logic
- [ ] Unit tests for capability detection
- [ ] Integration tests with actual model APIs
- [ ] Tests for all role configurations
- [ ] Tests for product-specific overrides

## Notes & Warnings

- Model IDs should be stable (don't change config between deployments)
- Failure counts should have TTL (don't permanently blacklist)
- Vision capability is required for style_refiner in full_mimic mode
- Landing/Card products prioritize aesthetic over raw generation quality
- Some model providers may not support all roles
- Log all model selections for debugging
- Consider cost implications when selecting models
