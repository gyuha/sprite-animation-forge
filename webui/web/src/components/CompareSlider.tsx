import { useState } from 'react'
import { Slider } from '@/components/ui/slider'
import { CHECKER } from '@/lib/background'

/** Original (left of the divider) vs background-removed (right) of the same sheet, stacked and clipped. */
export function CompareSlider({ original, clean }: { original: string; clean: string }) {
  const [pos, setPos] = useState(50)
  return (
    <div className="space-y-2" data-testid="compare-slider">
      <div className="relative overflow-hidden rounded-md border" style={CHECKER}>
        <img src={clean} alt="배경 제거" className="block w-full" data-testid="compare-clean" />
        <img
          src={original}
          alt="원본"
          className="absolute inset-0 block w-full"
          style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
          data-testid="compare-original"
        />
        <div className="pointer-events-none absolute inset-y-0 w-px bg-primary" style={{ left: `${pos}%` }} />
      </div>
      <Slider min={0} max={100} value={[pos]} onValueChange={([v]) => setPos(v)} aria-label="원본과 배경 제거 비교" data-testid="compare-position" />
    </div>
  )
}
