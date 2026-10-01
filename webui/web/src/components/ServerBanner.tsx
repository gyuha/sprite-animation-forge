import { WifiOff } from 'lucide-react'
import { ApiError } from '@/api/client'
import { useHealth } from '@/api/queries'
import { useEventStreamConnected } from '@/api/sse'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'

/** docs/09 8: shown while the event stream is down or /api/health cannot be reached; both reconnect by themselves. */
export function ServerBanner() {
  const streamUp = useEventStreamConnected()
  const health = useHealth()
  const unreachable = health.error instanceof ApiError && health.error.code === 'network_error'
  if (streamUp && !unreachable) return null
  return (
    <Alert variant="destructive" className="rounded-none border-x-0" data-testid="server-unreachable-banner">
      <WifiOff />
      <AlertTitle>서버에 연결할 수 없습니다</AlertTitle>
      <AlertDescription>자동으로 다시 연결하는 중입니다 (최대 30초 간격). 서버가 실행 중인지 확인하세요.</AlertDescription>
    </Alert>
  )
}
