import { Routes, Route } from 'react-router-dom'
import { HomePage } from '@/pages/HomePage'
import { ProjectPage } from '@/pages/ProjectPage'
import { SettingsPage } from '@/pages/SettingsPage'
import { ExecutionPage } from '@/pages/ExecutionPage'
import { Toaster } from '@/components/ui/toaster'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'

function App() {
  const isOnline = useOnlineStatus()

  return (
    <div className="min-h-screen bg-background text-foreground">
      {!isOnline ? (
        <div
          className="bg-destructive px-4 py-2 text-center text-xs font-medium text-destructive-foreground"
          role="status"
          aria-live="polite"
        >
          You are offline. Changes will sync when the connection returns.
        </div>
      ) : null}
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/project/:id" element={<ProjectPage />} />
        <Route path="/project/:id/flow" element={<ExecutionPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Routes>
      <Toaster />
    </div>
  )
}

export default App
