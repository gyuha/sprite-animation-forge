import { NavLink, Outlet, useMatch } from 'react-router-dom'
import { useJobEvents } from '@/api/sse'
import { BatchNotifier } from '@/components/BatchNotifier'
import { CodexStatusBadge } from '@/components/CodexStatusBadge'
import { JobTray } from '@/components/JobTray'
import { ServerBanner } from '@/components/ServerBanner'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

const NAV = [
  { to: '/', label: '캐릭터', end: true },
  { to: '/new', label: '새 캐릭터', end: false },
  { to: '/status', label: '상태', end: false },
]

export default function AppLayout() {
  useJobEvents()
  const cid = useMatch('/c/:cid/*')?.params.cid
  return (
    <TooltipProvider>
      <header className="flex h-14 items-center gap-6 border-b px-6">
        <span className="font-semibold">Sprite Animation Forge</span>
        <nav className="flex gap-4 text-sm">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) => cn('text-muted-foreground hover:text-foreground', isActive && 'font-medium text-foreground')}
            >
              {n.label}
            </NavLink>
          ))}
          {cid && (
            <NavLink to={`/c/${cid}/studio`} className={({ isActive }) => cn('text-muted-foreground hover:text-foreground', isActive && 'font-medium text-foreground')} data-testid="nav-studio">
              스튜디오
            </NavLink>
          )}
          {cid && (
            <NavLink to={`/c/${cid}/view`} className={({ isActive }) => cn('text-muted-foreground hover:text-foreground', isActive && 'font-medium text-foreground')} data-testid="nav-view">
              애니메이션
            </NavLink>
          )}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <CodexStatusBadge />
          <JobTray />
        </div>
      </header>
      <ServerBanner />
      <main className="p-6">
        <Outlet />
      </main>
      <BatchNotifier />
      <Toaster />
    </TooltipProvider>
  )
}
