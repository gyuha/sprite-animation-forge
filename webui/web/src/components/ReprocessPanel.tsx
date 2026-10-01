import { useEffect, useRef, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { ENUMS, PLAN_KEYS, SLIDERS, patchValues, valuesToSet, type ProcessSet, type ReprocessValues } from '@/lib/reprocess'
import { cn } from '@/lib/utils'

export const REPROCESS_DEBOUNCE_MS = 300

const ENUM_LABELS: { key: keyof typeof ENUMS; label: string }[] = [
  { key: 'anchor', label: '기준점' },
  { key: 'x_anchor', label: '가로 기준' },
  { key: 'scale_strategy', label: '크기 전략' },
  { key: 'components', label: '조각 처리' },
]

interface Props {
  /** values of the attempt as last processed; remount (key) to load new ones */
  initial: ReprocessValues
  /** the plan's own values for anchor/x_anchor/scale_strategy/components: differing controls are highlighted */
  planDefaults: Pick<ReprocessValues, (typeof PLAN_KEYS)[number]>
  /** called 300 ms after the last change with every parameter */
  onApply: (set: ProcessSet) => void
  /** "기본값으로 저장": the four plan-level parameters */
  onSaveDefaults: (set: Record<string, string>) => void
  busy?: boolean
  disabledReason?: string | null
  defaultOpen?: boolean
}

/** docs/09 6: changing a control reprocesses the attempt after a short pause (no raw regeneration). */
export function ReprocessPanel({ initial, planDefaults, onApply, onSaveDefaults, busy, disabledReason, defaultOpen = false }: Props) {
  const [values, setValues] = useState(initial)
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const apply = useRef(onApply)
  apply.current = onApply
  useEffect(() => () => clearTimeout(timer.current), [])

  const change = (patch: Partial<ReprocessValues>) => {
    const next = patchValues(values, patch)
    setValues(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => apply.current(valuesToSet(next)), REPROCESS_DEBOUNCE_MS)
  }
  const differs = (k: (typeof PLAN_KEYS)[number]) => values[k] !== planDefaults[k]

  return (
    <Collapsible defaultOpen={defaultOpen} className="space-y-3" data-testid="reprocess-panel">
      <CollapsibleTrigger asChild>
        <Button variant="ghost" size="sm" className="w-full justify-between" data-testid="reprocess-toggle">
          세부 조정 {busy && <span className="text-xs text-muted-foreground">처리 중...</span>}
          <ChevronDown />
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent className="space-y-4">
        {ENUM_LABELS.map(({ key, label }) => (
          <div key={key} className="space-y-1" data-changed={differs(key)}>
            <Label className={cn(differs(key) && 'font-bold text-primary')}>{label}</Label>
            <Select value={values[key]} onValueChange={(v) => change({ [key]: v })} disabled={!!disabledReason}>
              <SelectTrigger className="w-full" data-testid={`reprocess-${key}`}><SelectValue /></SelectTrigger>
              <SelectContent>
                {ENUMS[key].map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        ))}
        {SLIDERS.map(({ key, label, min, max }) => (
          <div key={key} className="space-y-1.5">
            <div className="flex justify-between text-sm">
              <Label>{label}</Label>
              <span className="tabular-nums text-muted-foreground" data-testid={`reprocess-${key}-value`}>{values[key] as number}</span>
            </div>
            <Slider min={min} max={max} step={1} value={[values[key] as number]} disabled={!!disabledReason} onValueChange={([v]) => change({ [key]: v })} aria-label={label} data-testid={`reprocess-${key}`} />
          </div>
        ))}
        <div className="flex items-center justify-between">
          <Label htmlFor="reprocess-despill">가장자리 색 번짐 제거</Label>
          <Switch id="reprocess-despill" checked={values.despill} disabled={!!disabledReason} onCheckedChange={(v) => change({ despill: v })} data-testid="reprocess-despill" />
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={!!disabledReason || PLAN_KEYS.every((k) => !differs(k))} onClick={() => change({ ...planDefaults })} data-testid="reprocess-reset">
            기본값으로
          </Button>
          <Button variant="secondary" size="sm" disabled={!!disabledReason} onClick={() => onSaveDefaults(Object.fromEntries(PLAN_KEYS.map((k) => [k, values[k]])))} data-testid="reprocess-save">
            기본값으로 저장
          </Button>
        </div>
      </CollapsibleContent>
    </Collapsible>
  )
}
