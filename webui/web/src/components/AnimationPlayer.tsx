import { useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Pause, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Slider } from '@/components/ui/slider'
import { Toggle } from '@/components/ui/toggle'
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { BACKGROUNDS, type BackgroundKey } from '@/lib/background'
import { alphaBBox, frameAt, framesVersion, originFor, stepFrame } from '@/lib/player'
import { cn } from '@/lib/utils'

export type Overlay = 'baseline' | 'anchor' | 'bbox' | 'onion'
const OVERLAYS: { key: Overlay; label: string }[] = [
  { key: 'baseline', label: '기준선' },
  { key: 'anchor', label: '중심선' },
  { key: 'bbox', label: 'bbox' },
  { key: 'onion', label: '어니언' },
]
const SCALES = [1, 2, 4]

interface Props {
  /** Output frame URLs (`/files/...?v=hash`), in order. */
  frames: string[]
  /** Plan fps; the slider (1-30) only changes the preview. */
  fps: number
  loop: boolean
  cell: { w: number; h: number }
  /** process.json derived.baseline_y (output pixels) */
  baselineY?: number | null
  /** nearest-neighbour scaling for pixel-art styles */
  pixelated?: boolean
  /** playback and overlay state live in the page so keyboard shortcuts and the frame grid can drive them */
  playing: boolean
  onPlayingChange: (playing: boolean) => void
  frame: number
  onFrameChange: (frame: number) => void
  overlays: Overlay[]
  onOverlaysChange: (overlays: Overlay[]) => void
  /** previous result stays visible but faded while a reprocess runs */
  dimmed?: boolean
}

/** Canvas playback of an attempt's frames (docs/09 5): rAF timing from elapsed time, no GIF. */
export function AnimationPlayer({ frames, fps: planFps, loop, cell, baselineY, pixelated = false, playing, onPlayingChange, frame, onFrameChange, overlays, onOverlaysChange, dimmed }: Props) {
  const [fps, setFps] = useState(planFps)
  const [scale, setScale] = useState(2)
  const [bg, setBg] = useState<BackgroundKey>('checker')
  const [loaded, setLoaded] = useState(0)
  const canvas = useRef<HTMLCanvasElement>(null)
  const images = useRef<HTMLImageElement[]>([])
  const bboxes = useRef(new Map<string, [number, number, number, number] | null>())
  const frameRef = useRef(frame)
  frameRef.current = frame
  const count = frames.length
  const shown = Math.min(frame, Math.max(count - 1, 0))

  useEffect(() => setFps(planFps), [planFps])

  // (Re)load the frame images whenever the URL list (including hashes) changes; old ones stay drawn until then.
  useEffect(() => {
    let alive = true
    const next = frames.map((url) => {
      const img = new Image()
      img.onload = () => alive && setLoaded((n) => n + 1)
      img.src = url
      return img
    })
    images.current = next
    return () => { alive = false }
  }, [frames])

  useEffect(() => {
    if (!playing || count < 2) return
    const origin = performance.now() - originFor(frameRef.current, fps)
    let raf = requestAnimationFrame(function tick(now) {
      const next = frameAt(now - origin, fps, count, loop)
      if (next !== frameRef.current) onFrameChange(next)
      raf = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(raf)
  }, [playing, fps, count, loop, onFrameChange])

  useEffect(() => {
    const ctx = canvas.current?.getContext('2d')
    const img = images.current[shown]
    if (!ctx) return
    ctx.clearRect(0, 0, cell.w * scale, cell.h * scale)
    ctx.imageSmoothingEnabled = !pixelated
    const draw = (i: HTMLImageElement | undefined, alpha = 1) => {
      if (!i?.complete || !i.naturalWidth) return
      ctx.globalAlpha = alpha
      ctx.drawImage(i, 0, 0, cell.w * scale, cell.h * scale)
      ctx.globalAlpha = 1
    }
    if (overlays.includes('onion') && count > 1) draw(images.current[stepFrame(shown, -1, count)], 0.3)
    draw(img)
    ctx.lineWidth = 1
    const line = (x1: number, y1: number, x2: number, y2: number, color: string) => {
      ctx.strokeStyle = color
      ctx.beginPath()
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()
    }
    if (overlays.includes('baseline') && baselineY != null) line(0, (baselineY + 0.5) * scale, cell.w * scale, (baselineY + 0.5) * scale, '#dc2626')
    if (overlays.includes('anchor')) {
      line((cell.w / 2) * scale, 0, (cell.w / 2) * scale, cell.h * scale, '#f97316')
      if (baselineY != null) {
        ctx.fillStyle = '#f97316'
        ctx.fillRect((cell.w / 2) * scale - 2, (baselineY + 0.5) * scale - 2, 4, 4)
      }
    }
    if (overlays.includes('bbox') && img?.complete && img.naturalWidth) {
      if (!bboxes.current.has(img.src)) {
        const probe = document.createElement('canvas')
        probe.width = img.naturalWidth
        probe.height = img.naturalHeight
        const pctx = probe.getContext('2d')
        pctx?.drawImage(img, 0, 0)
        bboxes.current.set(img.src, pctx ? alphaBBox(pctx.getImageData(0, 0, probe.width, probe.height).data, probe.width, probe.height) : null)
      }
      const b = bboxes.current.get(img.src)
      if (b) {
        ctx.strokeStyle = '#2563eb'
        ctx.strokeRect(b[0] * scale + 0.5, b[1] * scale + 0.5, (b[2] - b[0]) * scale - 1, (b[3] - b[1]) * scale - 1)
      }
    }
  }, [shown, loaded, scale, overlays, baselineY, cell.w, cell.h, pixelated, count])

  return (
    <div className="space-y-3" data-testid="animation-player">
      <div className={cn('inline-block max-w-full overflow-auto rounded-md border transition-opacity', dimmed && 'opacity-50')} style={BACKGROUNDS[bg].style}>
        <canvas
          ref={canvas}
          width={cell.w * scale}
          height={cell.h * scale}
          className="block"
          data-testid="preview-canvas"
          data-version={framesVersion(frames)}
          data-frame={shown}
          data-frame-count={count}
          data-playing={playing}
          data-overlays={overlays.join(',')}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="outline" size="icon" aria-label="이전 프레임" data-testid="player-prev" onClick={() => onFrameChange(stepFrame(shown, -1, count))}>
          <ChevronLeft />
        </Button>
        <Button size="icon" aria-label={playing ? '정지' : '재생'} data-testid="player-play" onClick={() => onPlayingChange(!playing)}>
          {playing ? <Pause /> : <Play />}
        </Button>
        <Button variant="outline" size="icon" aria-label="다음 프레임" data-testid="player-next" onClick={() => onFrameChange(stepFrame(shown, 1, count))}>
          <ChevronRight />
        </Button>
        <span className="w-14 text-sm tabular-nums" data-testid="player-frame">{count ? `${shown + 1} / ${count}` : '-'}</span>
        <span className="text-sm text-muted-foreground tabular-nums" data-testid="player-fps-value">{fps}fps</span>
        <Slider className="w-32" min={1} max={30} step={1} value={[fps]} onValueChange={([v]) => setFps(v)} aria-label="fps" data-testid="player-fps" />
        <ToggleGroup type="single" variant="outline" size="sm" value={String(scale)} onValueChange={(v) => v && setScale(Number(v))} data-testid="player-scale">
          {SCALES.map((s) => <ToggleGroupItem key={s} value={String(s)} data-testid={`player-scale-${s}`}>{s}x</ToggleGroupItem>)}
        </ToggleGroup>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <ToggleGroup type="single" variant="outline" size="sm" value={bg} onValueChange={(v) => v && setBg(v as BackgroundKey)} data-testid="player-bg">
          {(Object.keys(BACKGROUNDS) as BackgroundKey[]).map((k) => (
            <ToggleGroupItem key={k} value={k} data-testid={`player-bg-${k}`}>{BACKGROUNDS[k].label}</ToggleGroupItem>
          ))}
        </ToggleGroup>
        {OVERLAYS.map(({ key, label }) => (
          <Toggle
            key={key}
            variant="outline"
            size="sm"
            pressed={overlays.includes(key)}
            onPressedChange={(on) => onOverlaysChange(on ? [...overlays, key] : overlays.filter((k) => k !== key))}
            data-testid={`player-overlay-${key}`}
          >
            {label}
          </Toggle>
        ))}
      </div>
    </div>
  )
}
