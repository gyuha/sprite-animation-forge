/**
 * 애니메이션 뷰어. 경로 /c/:cid/view. 채택된 모든 액션×방향을 하나의 rAF 시계로 동시에 재생한다. data-testid:
 *   viewer-page                   화면 루트
 *   viewer-play-all               전체 재생/일시정지 (data-playing)
 *   viewer-speed-<0.5|1|2>, viewer-scale-<1|2|3|4>, viewer-bg-<checker|dark|light|green>   공통 컨트롤
 *   viewer-grid                   타일 영역 (data-playing, data-speed, data-scale, data-bg)
 *   viewer-tile-<unit>            재생 가능한 타일의 canvas 자체 (unit = walk/down 처럼 슬래시 유지).
 *                                 data-unit, data-frame(그려진 프레임), data-frame-count, data-painted("true"는 한 번 이상 그린 뒤)
 *   viewer-frame-<unit>           타일의 프레임 카운터 ("3 / 6")
 *   viewer-tile-missing-<unit>    미채택 플레이스홀더 (스튜디오 링크 포함). 접두사 viewer-tile- 을 공유하므로 canvas 만 세려면 `canvas[data-testid^="viewer-tile-"]`
 *   viewer-zoom-dialog            타일 클릭 시 열리는 확대 플레이어
 *   viewer-empty                  플랜이 없거나 채택된 unit 이 하나도 없을 때
 */
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Pause, Play } from 'lucide-react'
import { useCharacter, usePlan } from '@/api/queries'
import { AnimationPlayer, type Overlay } from '@/components/AnimationPlayer'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { BACKGROUNDS, type BackgroundKey } from '@/lib/background'
import type { Plan } from '@/lib/plan'
import type { UnitRow } from '@/lib/studio'
import { SCALES, SPEEDS, buildTiles, playableCount, studioHref, tileFrame, type Tile } from '@/lib/viewer'

/** Smallest tile column (px) at 1x: label and counter fit even for 64px cells. */
const MIN_TILE = 160
const TILE_PADDING = 16

type Subscriber = (elapsedMs: number) => void
interface Clock { subscribe: (fn: Subscriber) => () => void }

/**
 * The one requestAnimationFrame loop of the page. While `playing`, elapsed time accumulates and every subscribed tile
 * is told the new elapsed value; paused, the loop stops and elapsed is kept, so resuming continues where it stopped.
 * A new subscriber gets the current elapsed time immediately.
 */
function useSharedClock(playing: boolean): Clock {
  const elapsed = useRef(0)
  const subscribers = useRef(new Set<Subscriber>())
  useEffect(() => {
    if (!playing) return
    let last = performance.now()
    let raf = requestAnimationFrame(function tick(now) {
      elapsed.current += Math.max(0, now - last)
      last = now
      subscribers.current.forEach((fn) => fn(elapsed.current))
      raf = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(raf)
  }, [playing])
  return useMemo(() => ({
    subscribe: (fn) => {
      subscribers.current.add(fn)
      fn(elapsed.current)
      return () => { subscribers.current.delete(fn) }
    },
  }), [])
}

interface TileViewProps { tile: Tile; cell: { w: number; h: number }; scale: number; speed: number; bg: BackgroundKey; clock: Clock; onOpen: () => void }

/** One playable tile: preloads its frames once, draws on the canvas only when the shown frame changes. */
function PlayableTile({ tile, cell, scale, speed, bg, clock, onOpen }: TileViewProps) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const images = useRef<HTMLImageElement[]>([])
  const [loaded, setLoaded] = useState(0)
  const [frame, setFrame] = useState(0)
  const [painted, setPainted] = useState(false)
  const urlsKey = tile.urls.join('|')

  useEffect(() => {
    let alive = true
    images.current = tile.urls.map((url) => {
      const img = new Image()
      img.onload = () => alive && setLoaded((n) => n + 1)
      img.src = url
      return img
    })
    return () => { alive = false }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlsKey])

  useEffect(
    () => clock.subscribe((ms) => setFrame(tileFrame(ms, tile.fps, tile.frames, tile.loop, speed))),
    [clock, tile.fps, tile.frames, tile.loop, speed],
  )

  useEffect(() => {
    const ctx = canvas.current?.getContext('2d')
    const img = images.current[frame]
    if (!ctx || !img?.complete || !img.naturalWidth) return
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, cell.w, cell.h)
    ctx.drawImage(img, 0, 0, cell.w, cell.h)
    setPainted(true)
  }, [frame, loaded, cell.w, cell.h, urlsKey])

  return (
    <button type="button" onClick={onOpen} aria-label={`${tile.label} 확대`} className="flex flex-col items-center gap-2 rounded-lg border bg-card p-2 text-left transition-colors hover:bg-muted/50">
      <div className="max-w-full overflow-hidden rounded" style={BACKGROUNDS[bg].style}>
        <canvas
          ref={canvas}
          width={cell.w}
          height={cell.h}
          style={{ width: cell.w * scale, height: cell.h * scale, imageRendering: 'pixelated' }}
          className="block max-w-full"
          data-testid={`viewer-tile-${tile.unit}`}
          data-unit={tile.unit}
          data-frame={frame}
          data-frame-count={tile.frames}
          data-painted={painted}
        />
      </div>
      <div className="flex w-full items-center justify-between gap-2 text-xs">
        <span className="font-medium">{tile.label}</span>
        <span className="text-muted-foreground tabular-nums" data-testid={`viewer-frame-${tile.unit}`}>{frame + 1} / {tile.frames}</span>
      </div>
    </button>
  )
}

function MissingTile({ cid, tile, cell, scale }: { cid: string; tile: Tile; cell: { w: number; h: number }; scale: number }) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-2" data-testid={`viewer-tile-missing-${tile.unit}`}>
      <div className="flex max-w-full items-center justify-center rounded bg-muted text-sm text-muted-foreground" style={{ width: cell.w * scale, height: cell.h * scale }}>
        미채택
      </div>
      <div className="flex w-full items-center justify-between gap-2 text-xs">
        <span className="font-medium">{tile.label}</span>
        <Link className="underline" to={studioHref(cid, tile)}>스튜디오에서 만들기</Link>
      </div>
    </div>
  )
}

export default function Viewer() {
  const { cid = '' } = useParams()
  const plan = usePlan(cid)
  const character = useCharacter(cid)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState<number>(1)
  const [scale, setScale] = useState<number>(2)
  const [bg, setBg] = useState<BackgroundKey>('checker')
  const [zoom, setZoom] = useState<Tile | null>(null)
  const [zoomPlaying, setZoomPlaying] = useState(true)
  const [zoomFrame, setZoomFrame] = useState(0)
  const [zoomOverlays, setZoomOverlays] = useState<Overlay[]>([])
  const clock = useSharedClock(playing)

  const p = plan.data?.plan as Plan | undefined
  const rows = (character.data?.status.units ?? []) as unknown as UnitRow[]
  const tileRows = useMemo(() => (p ? buildTiles(cid, p, rows) : []), [cid, p, rows])

  const open = (tile: Tile) => { setZoom(tile); setZoomFrame(0); setZoomPlaying(true) }
  const header = (
    <div className="flex flex-wrap items-center gap-3">
      <Button asChild variant="ghost" size="sm"><Link to="/"><ArrowLeft /> {cid}</Link></Button>
      <h1 className="text-xl font-semibold">애니메이션</h1>
    </div>
  )

  if (plan.isPending || character.isPending) return <div className="space-y-4" data-testid="viewer-page">{header}<Skeleton className="h-96 w-full" /></div>
  const empty = !p || character.isError || playableCount(tileRows) === 0
  const cell = (p?.cell ?? { w: 128, h: 128 }) as { w: number; h: number }
  const column = Math.max(MIN_TILE, cell.w * scale + TILE_PADDING)

  return (
    <div className="space-y-5" data-testid="viewer-page">
      {header}
      {empty ? (
        <Alert data-testid="viewer-empty">
          <AlertTitle>재생할 애니메이션이 없습니다</AlertTitle>
          <AlertDescription>
            {!p ? '플랜이 아직 없습니다.' : '채택된 액션이 없습니다.'}{' '}
            <Link className="underline" to={p ? `/c/${cid}/studio` : `/c/${cid}/plan`}>{p ? '스튜디오로' : '플랜 만들기'}</Link>
          </AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-4">
            <Button variant="outline" onClick={() => setPlaying((v) => !v)} data-testid="viewer-play-all" data-playing={playing}>
              {playing ? <><Pause /> 모두 정지</> : <><Play /> 모두 재생</>}
            </Button>
            <ToggleGroup type="single" variant="outline" size="sm" value={String(speed)} onValueChange={(v) => v && setSpeed(Number(v))} aria-label="속도">
              {SPEEDS.map((s) => <ToggleGroupItem key={s} value={String(s)} data-testid={`viewer-speed-${s}`}>{s}x</ToggleGroupItem>)}
            </ToggleGroup>
            <ToggleGroup type="single" variant="outline" size="sm" value={String(scale)} onValueChange={(v) => v && setScale(Number(v))} aria-label="배율">
              {SCALES.map((s) => <ToggleGroupItem key={s} value={String(s)} data-testid={`viewer-scale-${s}`}>{s}x</ToggleGroupItem>)}
            </ToggleGroup>
            <ToggleGroup type="single" variant="outline" size="sm" value={bg} onValueChange={(v) => v && setBg(v as BackgroundKey)} aria-label="배경">
              {(Object.keys(BACKGROUNDS) as BackgroundKey[]).map((k) => (
                <ToggleGroupItem key={k} value={k} data-testid={`viewer-bg-${k}`}>{BACKGROUNDS[k].label}</ToggleGroupItem>
              ))}
            </ToggleGroup>
          </div>
          <div className="space-y-6" data-testid="viewer-grid" data-playing={playing} data-speed={speed} data-scale={scale} data-bg={bg}>
            {tileRows.map((row) => (
              <section key={row.action} className="space-y-2">
                {row.tiles.length > 1 && <h2 className="text-sm font-semibold">{row.action}</h2>}
                <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${column}px, max-content))` }}>
                  {row.tiles.map((t) => t.state === 'playable'
                    ? <PlayableTile key={t.unit} tile={t} cell={cell} scale={scale} speed={speed} bg={bg} clock={clock} onOpen={() => open(t)} />
                    : <MissingTile key={t.unit} cid={cid} tile={t} cell={cell} scale={scale} />)}
                </div>
              </section>
            ))}
          </div>
        </>
      )}
      <Dialog open={zoom !== null} onOpenChange={(o) => !o && setZoom(null)}>
        <DialogContent className="max-h-[90vh] max-w-3xl overflow-auto" data-testid="viewer-zoom-dialog">
          <DialogHeader>
            <DialogTitle>{zoom?.label}</DialogTitle>
            <DialogDescription>{zoom?.frames}프레임 · {zoom?.loop ? '반복' : '1회 재생'}</DialogDescription>
          </DialogHeader>
          {zoom && (
            <AnimationPlayer
              frames={zoom.urls}
              fps={zoom.fps}
              loop={zoom.loop}
              cell={cell}
              pixelated
              playing={zoomPlaying}
              onPlayingChange={setZoomPlaying}
              frame={zoomFrame}
              onFrameChange={setZoomFrame}
              overlays={zoomOverlays}
              onOverlaysChange={setZoomOverlays}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}
