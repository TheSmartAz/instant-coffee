import * as React from 'react'
import { Routes, Route } from 'react-router-dom'
import { Toaster } from '@/components/ui/toaster'
import { ErrorBoundary } from '@/components/ErrorBoundary'
import { useOnlineStatus } from '@/hooks/useOnlineStatus'

const HomePage = React.lazy(() =>
  import('@/pages/HomePage').then((module) => ({ default: module.HomePage }))
)

const ProjectPage = React.lazy(() =>
  import('@/pages/ProjectPage').then((module) => ({ default: module.ProjectPage }))
)

const SettingsPage = React.lazy(() =>
  import('@/pages/SettingsPage').then((module) => ({ default: module.SettingsPage }))
)

const ExecutionPage = React.lazy(() =>
  import('@/pages/ExecutionPage').then((module) => ({ default: module.ExecutionPage }))
)

function App() {
  const isOnline = useOnlineStatus()

  return (
    <ErrorBoundary>
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
        <React.Suspense
          fallback={
            <div className="flex h-[calc(100vh-56px)] items-center justify-center text-sm text-muted-foreground">
              Loading...
            </div>
          }
        >
          <Routes>
            <Route path="/" element={<ErrorBoundary><HomePage /></ErrorBoundary>} />
            <Route path="/project/:id" element={<ErrorBoundary><ProjectPage /></ErrorBoundary>} />
            <Route path="/project/:id/flow" element={<ErrorBoundary><ExecutionPage /></ErrorBoundary>} />
            <Route path="/settings" element={<ErrorBoundary><SettingsPage /></ErrorBoundary>} />
          </Routes>
        </React.Suspense>
        <Toaster />
      </div>
    </ErrorBoundary>
  )
}

export default App
