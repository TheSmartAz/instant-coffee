# Phase F5: Failure Handling UI - Testing Guide

## Quick Start

1. **Start the development server**:
   ```bash
   cd packages/web
   npm run dev
   ```

2. **Open the browser**: Navigate to `http://localhost:5176` (or the port shown in terminal)

3. **Test the failure dialog**: Type `demo-fail` in the input box and press Enter

## Demo Commands

### `demo`
Shows the normal execution flow with successful tasks.

### `demo-fail`
Shows a failure scenario with:
- Task 1: ✓ Completed (分析需求)
- Task 2: ✗ Failed (生成页面结构)
- Task 3: ⊘ Blocked (添加样式)
- Task 4: ⊘ Blocked (测试响应式布局)

The failure dialog will automatically appear after the events are processed.

## Testing the Failure Dialog

### Visual Elements to Verify

1. **Dialog Appearance**:
   - [ ] Modal overlay with semi-transparent black background
   - [ ] White dialog box centered on screen
   - [ ] Red alert icon and "任务执行失败" header
   - [ ] Close button (X) in top-right corner

2. **Task Information**:
   - [ ] Task title displayed: "生成页面结构"
   - [ ] Error message in red box: "API 调用超时: 无法连接到 Claude API 服务器..."
   - [ ] Retry count displayed: "已自动重试 2/3 次"

3. **Blocked Tasks Section**:
   - [ ] Shows "以下任务被阻塞 (2)"
   - [ ] Lists blocked tasks: "添加样式" and "测试响应式布局"
   - [ ] Orange background for blocked task items

4. **Action Buttons**:
   - [ ] Blue "重试" button (full width)
   - [ ] Amber "修改需求后重试" button (full width)
   - [ ] Gray "跳过此任务" button (half width)
   - [ ] Red "终止执行" button (half width)

### Interactive Testing

#### Test 1: Retry Action
1. Click the "重试" button
2. Expected: Console log shows retry API call
3. Expected: Dialog closes after action completes

#### Test 2: Modify and Retry
1. Click "修改需求后重试" button
2. Expected: View changes to modification form
3. Expected: Shows "返回" button
4. Expected: Textarea pre-filled with task description
5. Expected: "提交并重试" button at bottom
6. Type new description in textarea
7. Click "提交并重试"
8. Expected: Console log shows modify API call
9. Expected: Dialog closes after action completes

#### Test 3: Skip Task
1. Click "跳过此任务" button
2. Expected: Console log shows skip API call
3. Expected: Dialog closes after action completes

#### Test 4: Abort Execution
1. Click "终止执行" button
2. Expected: View changes to abort confirmation
3. Expected: Shows warning icon and message
4. Expected: "确定要终止执行吗？" heading
5. Expected: Explanation text about consequences
6. Expected: "取消" and "确认终止" buttons
7. Click "取消"
8. Expected: Returns to main view
9. Click "终止执行" again
10. Click "确认终止"
11. Expected: Console log shows abort API call
12. Expected: Dialog closes after action completes

#### Test 5: Close Dialog
1. Click the X button in top-right corner
2. Expected: Dialog closes immediately
3. Expected: Can reopen by clicking failed task in TodoPanel

### Responsive Testing

Test on different screen sizes:
- [ ] Desktop (1920x1080)
- [ ] Tablet (768x1024)
- [ ] Mobile (375x667)

Verify:
- [ ] Dialog is centered on all screen sizes
- [ ] Dialog has proper margins (mx-4)
- [ ] Text is readable
- [ ] Buttons are clickable
- [ ] No horizontal scrolling

### Accessibility Testing

- [ ] Can close dialog with Escape key (not implemented yet)
- [ ] Can navigate buttons with Tab key
- [ ] Can activate buttons with Enter/Space
- [ ] Focus visible on interactive elements
- [ ] Color contrast meets WCAG standards

## Known Limitations

1. **API Integration**: Currently logs to console instead of making real API calls
2. **Session ID**: Demo mode doesn't have a real session ID for abort
3. **Real-time Updates**: Dialog doesn't auto-close when task status changes from backend
4. **Keyboard Shortcuts**: Escape key to close not implemented
5. **Focus Management**: Focus not trapped in dialog
6. **Screen Reader**: ARIA labels not added yet

## Next Steps for Production

1. **Connect to Real API**: Replace console.log with actual API calls
2. **Add Toast Notifications**: Show success/error messages after actions
3. **Implement Auto-close**: Close dialog when task status changes
4. **Add Keyboard Support**: Escape to close, Tab navigation
5. **Add Focus Trap**: Prevent focus from leaving dialog
6. **Add ARIA Labels**: Improve screen reader support
7. **Add Loading Spinners**: Show progress during API calls
8. **Add Error Handling**: Display API errors in dialog
9. **Add Animations**: Smooth transitions for view changes
10. **Add Confirmation**: Ask before closing if form has changes

## Troubleshooting

### Dialog doesn't appear
- Check console for errors
- Verify task status is 'failed'
- Check if failedTask state is set

### Buttons don't work
- Check console for API call logs
- Verify useTaskControl hook is imported
- Check if handlers are properly bound

### Styling issues
- Verify Tailwind CSS is loaded
- Check for CSS conflicts
- Inspect element in browser DevTools

## File Locations

- Components: `packages/web/src/components/Failure/`
- Hook: `packages/web/src/hooks/useTaskControl.ts`
- Integration: `packages/web/src/App.tsx`
- Types: `packages/web/src/types/plan.ts`, `packages/web/src/types/events.ts`
- API Config: `packages/web/src/api/config.ts`

## Screenshots

(Add screenshots here after testing)

1. Main failure dialog view
2. Modify task form view
3. Abort confirmation view
4. Blocked tasks display
5. Mobile view

---

**Last Updated**: 2026-01-30
**Status**: Ready for Testing
**Phase**: F5 - Failure Handling UI
