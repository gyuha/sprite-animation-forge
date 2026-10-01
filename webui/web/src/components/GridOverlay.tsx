import { gridGeometry, parseDerived } from '@/lib/grid'

/**
 * raw.png with process.json's grid drawn on top (docs/09 4 S5): green solid = gutter snapped, red dashed = no gutter,
 * per-frame bbox (blue) and anchor point (orange). The SVG uses the raw pixel space as its viewBox, so the browser does
 * the scaling and lines stay aligned at any displayed width.
 */
export function GridOverlay({ src, derived }: { src: string; derived: Record<string, unknown> | undefined | null }) {
  const parsed = parseDerived(derived)
  const geo = parsed ? gridGeometry(parsed) : null
  return (
    <div className="relative overflow-hidden rounded-md border bg-muted" data-testid="grid-overlay">
      <img src={src} alt="원본 sheet" className="block w-full" />
      {geo && (
        <svg viewBox={`0 0 ${geo.width} ${geo.height}`} className="absolute inset-0 h-full w-full" data-testid="grid-svg">
          {geo.lines.map(({ missing, ...l }, i) => (
            <line
              key={i}
              {...l}
              data-testid={missing ? 'grid-line-missing' : 'grid-line'}
              stroke={missing ? '#dc2626' : '#16a34a'}
              strokeWidth={2}
              strokeDasharray={missing ? '10 6' : undefined}
              vectorEffect="non-scaling-stroke"
            />
          ))}
          {geo.boxes.map((b) => (
            <rect key={b.index} x={b.x} y={b.y} width={b.width} height={b.height} data-testid="grid-bbox" fill="none" stroke="#2563eb" strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
          ))}
          {geo.anchors.map((a) => (
            <circle key={a.index} cx={a.x} cy={a.y} r={Math.max(geo.width, geo.height) / 150} data-testid="grid-anchor" fill="#f97316" />
          ))}
        </svg>
      )}
    </div>
  )
}
