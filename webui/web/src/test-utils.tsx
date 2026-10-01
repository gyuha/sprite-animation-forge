import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { qk } from '@/api/queries'
import type { JobSnapshot } from '@/api/sse'
import { TooltipProvider } from '@/components/ui/tooltip'

export function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

export function renderWithClient(ui: ReactElement, client = makeClient()) {
  return { client, ...render(<QueryClientProvider client={client}><TooltipProvider>{ui}</TooltipProvider></QueryClientProvider>) }
}

function LocationProbe() {
  return <div data-testid="location">{useLocation().pathname}</div>
}

/** Renders `element` at `route` (a react-router path pattern) opened at `path`; any other location shows LocationProbe. */
export function renderRoute(element: ReactElement, path: string, route: string, client = makeClient()) {
  return renderWithClient(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={route} element={element} />
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </MemoryRouter>,
    client,
  )
}

type Handler = unknown | ((init?: RequestInit) => unknown)

/** Replaces global fetch. Keys are "METHOD /path" (query string ignored); values are JSON bodies, Responses or functions of init. */
export function mockApi(routes: Record<string, Handler>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input).split('?')[0]}`
    if (!(key in routes)) return jsonResponse({ error: { code: 'not_found', message: `no mock for ${key}`, detail: {} } }, 404)
    const h = routes[key]
    const value = typeof h === 'function' ? (h as (i?: RequestInit) => unknown)(init) : h
    return value instanceof Response ? value : jsonResponse(value)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

export const apiError = (status: number, code: string, message: string) => jsonResponse({ error: { code, message, detail: {} } }, status)

/** JSON body of the last request made with `method` to `path`. */
export function lastBody(fetchMock: ReturnType<typeof mockApi>, method: string, path: string) {
  const calls = fetchMock.mock.calls.filter(([url, init]) => String(url).split('?')[0] === path && (init?.method ?? 'GET') === method)
  return JSON.parse(String(calls.at(-1)?.[1]?.body))
}

export function makeClientWithJobs(jobs: JobSnapshot[]) {
  const client = makeClient()
  client.setQueryData(qk.jobs, jobs)
  return client
}
