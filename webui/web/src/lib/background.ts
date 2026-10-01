import type { CSSProperties } from 'react'

export const CHECKER: CSSProperties = {
  backgroundImage: 'repeating-conic-gradient(#d4d4d8 0% 25%, #ffffff 0% 50%)',
  backgroundSize: '16px 16px',
}

/** Player background choices (docs/09 5). */
export const BACKGROUNDS = {
  checker: { label: '체커', style: CHECKER },
  dark: { label: '검정', style: { backgroundColor: '#111111' } as CSSProperties },
  light: { label: '흰색', style: { backgroundColor: '#ffffff' } as CSSProperties },
  green: { label: '초록', style: { backgroundColor: '#2f7d4a' } as CSSProperties },
}
export type BackgroundKey = keyof typeof BACKGROUNDS
