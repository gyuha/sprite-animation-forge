import { Plus, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { isHexColor } from '@/lib/color'

interface Props {
  label: string
  colors: string[]
  onChange: (colors: string[]) => void
  testId: string
}

/** Editable list of #RRGGBB colours. Invalid entries are flagged (aria-invalid) and kept; the parent blocks saving. */
export function PaletteEditor({ label, colors, onChange, testId }: Props) {
  const update = (i: number, value: string) => onChange(colors.map((c, j) => (j === i ? value : c)))
  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={testId}>
      {colors.map((c, i) => {
        const valid = isHexColor(c)
        return (
          <div key={i} className="flex items-center gap-1">
            <span
              className="size-6 shrink-0 rounded border"
              style={{ backgroundColor: valid ? c : 'transparent' }}
              aria-hidden
            />
            <Input
              className="w-28 font-mono"
              value={c}
              aria-label={`${label} ${i + 1}`}
              aria-invalid={!valid}
              title={valid ? undefined : '#RRGGBB 형식이어야 합니다'}
              data-testid={`${testId}-input-${i}`}
              onChange={(e) => update(i, e.target.value)}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              aria-label={`${label} ${i + 1} 삭제`}
              data-testid={`${testId}-remove-${i}`}
              onClick={() => onChange(colors.filter((_, j) => j !== i))}
            >
              <X />
            </Button>
          </div>
        )
      })}
      <Button type="button" variant="outline" size="sm" data-testid={`${testId}-add`} onClick={() => onChange([...colors, '#000000'])}>
        <Plus /> 색 추가
      </Button>
      {colors.some((c) => !isHexColor(c)) && (
        <p role="alert" className="w-full text-xs text-destructive">
          색은 #RRGGBB 형식이어야 합니다 (예: #C8281E)
        </p>
      )}
    </div>
  )
}
