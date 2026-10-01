import type { ReactElement } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { TooltipProvider } from '@/components/ui/tooltip'

export function makeClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

export function renderWithClient(ui: ReactElement, client = makeClient()) {
  return { client, ...render(<QueryClientProvider client={client}><TooltipProvider>{ui}</TooltipProvider></QueryClientProvider>) }
}
