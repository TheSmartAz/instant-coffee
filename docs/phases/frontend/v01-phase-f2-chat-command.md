# Phase F2: Chat Command Implementation

## Metadata

- **Category**: Frontend (CLI)
- **Priority**: P0 (Critical)
- **Estimated Complexity**: High
- **Parallel Development**: ⚠️ Has dependencies
- **Dependencies**:
  - **Blocked by**: F1 (CLI Framework), B1 (Chat API)
  - **Blocks**: None

## Goal

Build the interactive chat command with real-time conversation display, progress indicators, browser auto-launch, and seamless agent phase transitions.

## Detailed Tasks

### Task 1: Create Chat Command Handler

**Description**: Implement the main chat command with conversation loop.

**Implementation Details**:
- [ ] Create chat command with options (--output, --continue)
- [ ] Implement conversation loop (input → send → display → repeat)
- [ ] Add graceful exit handling (exit, quit, Ctrl+C)
- [ ] Generate or load session ID
- [ ] Display welcome message and instructions

**Files to modify/create**:
- `packages/cli/src/commands/chat.ts`

**Acceptance Criteria**:
- [ ] Command accepts user input in a loop
- [ ] Can exit cleanly with 'exit' or 'quit'
- [ ] Sessions are created or continued correctly
- [ ] Welcome message displays on start

---

### Task 2: Implement Interview Phase Display

**Description**: Build UI for displaying AI questions with formatting.

**Implementation Details**:
- [ ] Parse and format AI questions (emojis, options, hints)
- [ ] Display questions in readable format
- [ ] Handle user responses (text input)
- [ ] Show round numbers (Round 1/5, Round 2/5)

**Files to modify/create**:
- `packages/cli/src/commands/chat/interview-display.ts`

**Acceptance Criteria**:
- [ ] Questions are formatted beautifully
- [ ] Emojis and formatting render correctly
- [ ] User input is intuitive
- [ ] Round progress is visible

---

### Task 3: Implement Generation Phase Display

**Description**: Build progressive generation display with live updates.

**Implementation Details**:
- [ ] Create progress bar using ora
- [ ] Display stage updates (20%, 40%, 60%, 80%, 100%)
- [ ] Show stage descriptions (e.g., "✅ 页面结构已生成")
- [ ] Update spinner text in real-time
- [ ] Auto-open browser when complete

**Files to modify/create**:
- `packages/cli/src/commands/chat/generation-display.ts`

**Acceptance Criteria**:
- [ ] Progress updates display smoothly
- [ ] Spinner animations work correctly
- [ ] Stage descriptions are visible
- [ ] Browser opens automatically with file:// URL

---

### Task 4: Implement Refinement Phase Display

**Description**: Build UI for modification requests and confirmations.

**Implementation Details**:
- [ ] Display modification completion messages
- [ ] Show "Refresh browser" instructions
- [ ] Handle continuous refinement loop
- [ ] Display current version number

**Files to modify/create**:
- `packages/cli/src/commands/chat/refinement-display.ts`

**Acceptance Criteria**:
- [ ] Modification confirmations are clear
- [ ] Instructions for refreshing are visible
- [ ] User can continue modifying

---

### Task 5: Implement Error Handling and Retry Display

**Description**: Build UI for handling errors with retry feedback.

**Implementation Details**:
- [ ] Display retry attempts (1/3, 2/3, 3/3)
- [ ] Show error messages clearly
- [ ] Provide recovery suggestions
- [ ] Handle API connection failures

**Files to modify/create**:
- `packages/cli/src/commands/chat/error-display.ts`

**Acceptance Criteria**:
- [ ] Retry progress is visible
- [ ] Errors are displayed helpfully
- [ ] Recovery suggestions are clear
- [ ] Fatal errors stop gracefully

## Technical Specifications

### Chat Flow Implementation

```typescript
async function chatCommand(options: ChatOptions) {
  const sessionId = options.continue || generateSessionId();
  const outputDir = options.output || './instant-coffee-output';

  console.log(chalk.blue.bold('☕ Instant Coffee - 快速生成移动端页面'));
  console.log(chalk.gray('输入 "exit" 或 "quit" 退出\n'));

  while (true) {
    const userInput = await prompt('你: ');

    if (userInput === 'exit' || userInput === 'quit') {
      console.log(chalk.yellow('再见！👋'));
      break;
    }

    const spinner = ora('AI 思考中...').start();

    try {
      const response = await apiClient.post('/api/chat', {
        session_id: sessionId,
        message: userInput,
        output_dir: outputDir
      });

      spinner.stop();

      // Display based on phase
      if (response.phase === 'interview') {
        displayInterview(response);
      } else if (response.phase === 'generation') {
        displayGeneration(response);
      } else if (response.phase === 'refinement') {
        displayRefinement(response);
      }

      // Auto-open browser if preview URL provided
      if (response.preview_url) {
        await openBrowser(response.preview_url);
      }

    } catch (error) {
      spinner.stop();
      displayError(error);
    }
  }
}
```

### Progress Display Example

```typescript
function displayGeneration(response: ChatResponse) {
  const progress = response.progress || 0;

  const progressBar = '━'.repeat(Math.floor(progress / 5)) +
                      ' '.repeat(20 - Math.floor(progress / 5));

  console.log(chalk.blue('\nAI: '), response.message);
  console.log(`    ${progressBar} ${progress}%`);

  if (response.is_complete) {
    console.log(chalk.green('\n    ✅ 生成完成！'));
    console.log(chalk.gray(`    📂 预览: ${response.preview_url}`));
  }
}
```

## Testing Requirements

- [ ] Test full conversation flow (interview → generation → refinement)
- [ ] Test exit commands ('exit', 'quit', Ctrl+C)
- [ ] Test session continuation (--continue)
- [ ] Test progress display updates
- [ ] Test browser auto-open
- [ ] Test error handling and retry display
- [ ] Test long conversations

## Notes & Warnings

- **User Input**: Use inquirer for better input handling
- **Spinner**: Stop spinner before displaying new content
- **Browser Open**: Handle cases where browser fails to open
- **Long Messages**: Wrap long AI messages for readability
- **Streaming**: If backend supports streaming, implement progressive updates
- **Ctrl+C**: Handle gracefully, save state before exit
