# Phase F1: CLI Framework Setup

## Metadata

- **Category**: Frontend (CLI)
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Low
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: F2, F3, F4 (All CLI commands)

## Goal

Set up the CLI application framework with Commander.js, establish project structure, implement basic command routing, and create utility functions for styled output.

## Detailed Tasks

### Task 1: Project Setup

**Description**: Initialize the TypeScript CLI project with all dependencies.

**Implementation Details**:
- [ ] Create package.json with dependencies
- [ ] Set up TypeScript configuration
- [ ] Configure tsconfig.json for Node.js
- [ ] Add build scripts (dev, build, start)
- [ ] Configure npm bin for global installation
- [ ] Set up .env loading

**Files to modify/create**:
- `packages/cli/package.json`
- `packages/cli/tsconfig.json`
- `packages/cli/.env.example`

**Acceptance Criteria**:
- [ ] TypeScript compiles without errors
- [ ] Dev mode works with hot reload
- [ ] Can be installed globally via npm link
- [ ] Environment variables are loaded

---

### Task 2: Create Command Framework

**Description**: Set up Commander.js with base command structure.

**Implementation Details**:
- [ ] Create main CLI entry point
- [ ] Set up Commander.js program
- [ ] Add version and help commands
- [ ] Implement command routing
- [ ] Add global options (--verbose, --config)
- [ ] Create command registration system

**Files to modify/create**:
- `packages/cli/src/index.ts`
- `packages/cli/src/commands/index.ts`

**Acceptance Criteria**:
- [ ] `instant-coffee --help` displays help
- [ ] `instant-coffee --version` shows version
- [ ] Command routing works correctly
- [ ] Unknown commands show helpful error

---

### Task 3: Create Logger Utility

**Description**: Build styled console output utility using Chalk.

**Implementation Details**:
- [ ] Create Logger class with color methods
- [ ] Implement success(), error(), warning(), info() methods
- [ ] Add box() for framed messages
- [ ] Add progress() for progress bars
- [ ] Add table() for formatted tables
- [ ] Support verbose mode

**Files to modify/create**:
- `packages/cli/src/utils/logger.ts`

**Acceptance Criteria**:
- [ ] Colors display correctly in terminal
- [ ] All message types render properly
- [ ] Verbose mode toggles detailed output
- [ ] Works across different terminals

---

### Task 4: Create API Client

**Description**: Build HTTP client for backend API communication.

**Implementation Details**:
- [ ] Create ApiClient class with axios
- [ ] Implement request/response interceptors
- [ ] Add error handling and retries
- [ ] Support streaming responses
- [ ] Add timeout configuration
- [ ] Implement base URL configuration

**Files to modify/create**:
- `packages/cli/src/utils/api-client.ts`
- `packages/cli/src/config.ts`

**Acceptance Criteria**:
- [ ] Can make requests to backend API
- [ ] Error handling works correctly
- [ ] Streaming responses are supported
- [ ] Timeouts are properly handled

---

### Task 5: Create Browser Utility

**Description**: Build utility to auto-open browser for preview.

**Implementation Details**:
- [ ] Create browser utility using 'open' package
- [ ] Support different browsers (default, chrome, firefox, safari)
- [ ] Handle file:// URLs correctly
- [ ] Add error handling for open failures

**Files to modify/create**:
- `packages/cli/src/utils/browser.ts`

**Acceptance Criteria**:
- [ ] Opens file:// URLs in default browser
- [ ] Works on macOS, Linux, Windows
- [ ] Fails gracefully if browser can't open
- [ ] Displays helpful error messages

## Technical Specifications

### Project Structure
```
packages/cli/
├── src/
│   ├── index.ts              # Main entry point
│   ├── config.ts             # Configuration
│   ├── commands/
│   │   ├── index.ts          # Command registration
│   │   ├── chat.ts           # Chat command (stub)
│   │   ├── history.ts        # History command (stub)
│   │   ├── export.ts         # Export command (stub)
│   │   ├── stats.ts          # Stats command (stub)
│   │   └── clean.ts          # Clean command
│   └── utils/
│       ├── logger.ts         # Styled output
│       ├── api-client.ts     # HTTP client
│       └── browser.ts        # Browser opener
├── package.json
├── tsconfig.json
└── .env.example
```

### Dependencies
```json
{
  "dependencies": {
    "commander": "^12.0.0",
    "axios": "^1.6.0",
    "chalk": "^5.3.0",
    "ora": "^8.0.0",
    "inquirer": "^9.2.0",
    "open": "^10.0.0",
    "dotenv": "^16.0.0"
  },
  "devDependencies": {
    "@types/node": "^20.0.0",
    "typescript": "^5.3.0",
    "tsx": "^4.0.0"
  }
}
```

### Logger API
```typescript
const logger = new Logger();

logger.success('✅ Generation complete!');
logger.error('❌ Failed to connect to API');
logger.warning('⚠️ Retrying...');
logger.info('📂 Preview: file:///.../index.html');

logger.box('☕ Instant Coffee', 'Quick mobile page generation');
logger.progress(60, 'Applying styles');
logger.table([
  ['Session', 'Title', 'Updated'],
  ['abc123', 'Activity Page', '2025-01-30']
]);
```

## Testing Requirements

- [ ] Test command parsing and routing
- [ ] Test logger output formatting
- [ ] Test API client requests
- [ ] Test browser opening
- [ ] Test error handling
- [ ] Test environment variable loading

## Notes & Warnings

- **Global Installation**: Use `npm link` for local development testing
- **Cross-platform**: Test on macOS, Linux, and Windows
- **Terminal Colors**: Some terminals don't support all colors
- **File URLs**: Browser handling of file:// varies by OS
- **API URL**: Default to http://localhost:8000, allow override via env
