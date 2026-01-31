# Phase F1: Web 前端骨架

## Metadata

- **Category**: Frontend
- **Priority**: P0 (Critical)
- **Estimated Complexity**: Medium
- **Parallel Development**: ✅ Can develop in parallel
- **Dependencies**:
  - **Blocked by**: None
  - **Blocks**: F2 (SSE 事件消费)

## Goal

搭建 Web 前端基础框架，包括项目初始化、基础布局、输入组件，为后续功能开发提供基础。

## Detailed Tasks

### Task 1: 项目初始化

**Description**: 使用 Vite + React + TypeScript 初始化前端项目

**Implementation Details**:
- [ ] 创建 Vite React TypeScript 项目
- [ ] 配置 Tailwind CSS
- [ ] 配置 ESLint 和 Prettier
- [ ] 添加基础依赖 (lucide-react, clsx)

**Files to modify/create**:
- `packages/web/package.json`
- `packages/web/vite.config.ts`
- `packages/web/tailwind.config.js`
- `packages/web/tsconfig.json`

**Acceptance Criteria**:
- [ ] `npm run dev` 可以启动开发服务器
- [ ] TypeScript 类型检查通过
- [ ] Tailwind CSS 样式生效

---

### Task 2: 创建基础布局

**Description**: 实现主页面布局结构

**Implementation Details**:
- [ ] 创建 App 组件
- [ ] 创建 Header 组件
- [ ] 创建 MainContent 区域
- [ ] 创建 InputArea 组件
- [ ] 实现响应式布局

**Files to modify/create**:
- `packages/web/src/App.tsx`
- `packages/web/src/components/Layout/Header.tsx`
- `packages/web/src/components/Layout/MainContent.tsx`
- `packages/web/src/components/Layout/InputArea.tsx`

**Acceptance Criteria**:
- [ ] 页面布局符合设计稿
- [ ] 响应式在桌面/平板/移动端正常显示
- [ ] Header 显示品牌标识

---

### Task 3: 实现输入组件

**Description**: 创建消息输入框和发送按钮

**Implementation Details**:
- [ ] 创建 MessageInput 组件
- [ ] 支持多行文本输入
- [ ] 实现 Enter 发送，Shift+Enter 换行
- [ ] 发送中禁用状态
- [ ] 添加发送按钮

**Files to modify/create**:
- `packages/web/src/components/Input/MessageInput.tsx`
- `packages/web/src/components/Input/SendButton.tsx`

**Acceptance Criteria**:
- [ ] 输入框可以输入多行文本
- [ ] Enter 键发送消息
- [ ] Shift+Enter 换行
- [ ] 发送中显示 loading 状态

---

### Task 4: 配置 API 客户端

**Description**: 创建与后端通信的 API 客户端

**Implementation Details**:
- [ ] 创建 API 配置
- [ ] 创建 fetch 封装
- [ ] 添加错误处理
- [ ] 配置 CORS

**Files to modify/create**:
- `packages/web/src/api/config.ts`
- `packages/web/src/api/client.ts`

**Acceptance Criteria**:
- [ ] 可以调用后端 API
- [ ] 错误处理正确
- [ ] 支持 SSE 连接

---

## Technical Specifications

### 项目结构

```
packages/web/
├── public/
│   └── favicon.ico
├── src/
│   ├── api/
│   │   ├── config.ts
│   │   └── client.ts
│   ├── components/
│   │   ├── Layout/
│   │   │   ├── Header.tsx
│   │   │   ├── MainContent.tsx
│   │   │   └── InputArea.tsx
│   │   └── Input/
│   │       ├── MessageInput.tsx
│   │       └── SendButton.tsx
│   ├── hooks/
│   │   └── useSSE.ts
│   ├── types/
│   │   └── events.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── package.json
├── vite.config.ts
├── tailwind.config.js
└── tsconfig.json
```

### package.json

```json
{
  "name": "@instant-coffee/web",
  "private": true,
  "version": "0.2.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "lucide-react": "^0.300.0",
    "clsx": "^2.1.0"
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^8.55.0",
    "eslint-plugin-react-hooks": "^4.6.0",
    "eslint-plugin-react-refresh": "^0.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0"
  }
}
```

### App.tsx

```tsx
// packages/web/src/App.tsx
import { useState } from 'react';
import { Header } from './components/Layout/Header';
import { MainContent } from './components/Layout/MainContent';
import { InputArea } from './components/Layout/InputArea';

function App() {
  const [isLoading, setIsLoading] = useState(false);

  const handleSend = async (message: string) => {
    setIsLoading(true);
    try {
      // TODO: 发送消息到后端
      console.log('Sending:', message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      <Header />
      <MainContent />
      <InputArea onSend={handleSend} isLoading={isLoading} />
    </div>
  );
}

export default App;
```

### Header.tsx

```tsx
// packages/web/src/components/Layout/Header.tsx
import { Coffee, Plus } from 'lucide-react';

export function Header() {
  return (
    <header className="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
      <div className="flex items-center gap-2">
        <Coffee className="w-6 h-6 text-amber-600" />
        <span className="text-lg font-semibold text-gray-800">
          Instant Coffee
        </span>
      </div>
      <button
        className="flex items-center gap-1 px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-md transition-colors"
        onClick={() => {
          // TODO: 新建会话
        }}
      >
        <Plus className="w-4 h-4" />
        新会话
      </button>
    </header>
  );
}
```

### MainContent.tsx

```tsx
// packages/web/src/components/Layout/MainContent.tsx
import { ReactNode } from 'react';

interface MainContentProps {
  children?: ReactNode;
}

export function MainContent({ children }: MainContentProps) {
  return (
    <main className="flex-1 overflow-y-auto p-4">
      {children || (
        <div className="flex items-center justify-center h-full text-gray-400">
          输入你想要的页面描述，开始生成
        </div>
      )}
    </main>
  );
}
```

### InputArea.tsx

```tsx
// packages/web/src/components/Layout/InputArea.tsx
import { MessageInput } from '../Input/MessageInput';
import { SendButton } from '../Input/SendButton';
import { useState } from 'react';

interface InputAreaProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export function InputArea({ onSend, isLoading }: InputAreaProps) {
  const [message, setMessage] = useState('');

  const handleSend = () => {
    if (message.trim() && !isLoading) {
      onSend(message.trim());
      setMessage('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-200 bg-white p-4">
      <div className="flex gap-2 max-w-4xl mx-auto">
        <MessageInput
          value={message}
          onChange={setMessage}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="描述你想要的页面..."
        />
        <SendButton onClick={handleSend} isLoading={isLoading} />
      </div>
    </div>
  );
}
```

### MessageInput.tsx

```tsx
// packages/web/src/components/Input/MessageInput.tsx
import { useRef, useEffect } from 'react';

interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  onKeyDown: (e: React.KeyboardEvent) => void;
  disabled: boolean;
  placeholder: string;
}

export function MessageInput({
  value,
  onChange,
  onKeyDown,
  disabled,
  placeholder,
}: MessageInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // 自动调整高度
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`;
    }
  }, [value]);

  return (
    <textarea
      ref={textareaRef}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      onKeyDown={onKeyDown}
      disabled={disabled}
      placeholder={placeholder}
      rows={1}
      className="flex-1 px-4 py-2 border border-gray-300 rounded-lg resize-none focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent disabled:bg-gray-100 disabled:cursor-not-allowed"
    />
  );
}
```

### SendButton.tsx

```tsx
// packages/web/src/components/Input/SendButton.tsx
import { Send, Loader2 } from 'lucide-react';

interface SendButtonProps {
  onClick: () => void;
  isLoading: boolean;
}

export function SendButton({ onClick, isLoading }: SendButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={isLoading}
      className="px-4 py-2 bg-amber-600 text-white rounded-lg hover:bg-amber-700 disabled:bg-amber-400 disabled:cursor-not-allowed transition-colors"
    >
      {isLoading ? (
        <Loader2 className="w-5 h-5 animate-spin" />
      ) : (
        <Send className="w-5 h-5" />
      )}
    </button>
  );
}
```

### API 配置

```typescript
// packages/web/src/api/config.ts
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  chat: `${API_BASE_URL}/api/chat`,
  chatStream: `${API_BASE_URL}/api/chat/stream`,
  plan: `${API_BASE_URL}/api/plan`,
  taskRetry: (id: string) => `${API_BASE_URL}/api/task/${id}/retry`,
  taskSkip: (id: string) => `${API_BASE_URL}/api/task/${id}/skip`,
  sessionAbort: (id: string) => `${API_BASE_URL}/api/session/${id}/abort`,
};
```

### Tailwind 配置

```javascript
// packages/web/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        amber: {
          50: '#fffbeb',
          100: '#fef3c7',
          200: '#fde68a',
          300: '#fcd34d',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          700: '#b45309',
          800: '#92400e',
          900: '#78350f',
        },
      },
    },
  },
  plugins: [],
}
```

## Testing Requirements

- [ ] 组件渲染测试
- [ ] 输入框交互测试
- [ ] 响应式布局测试
- [ ] 键盘快捷键测试

## Notes & Warnings

- 使用 Vite 的环境变量需要 `VITE_` 前缀
- 确保 CORS 配置正确，允许前端访问后端 API
- 移动端需要测试虚拟键盘弹出时的布局
- 考虑添加 PWA 支持以便移动端使用
