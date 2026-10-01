/** Character id / settings helpers shared by the new-character form. */

// Same rule as the CLI (sprite_forge.cli.CID_RE).
export const CID_RE = /^[a-z0-9][a-z0-9-]{0,39}$/
export const CID_RULE = '영문 소문자·숫자·하이픈(-)만 쓸 수 있고, 첫 글자는 영문 소문자 또는 숫자이며 최대 40자입니다'

export function validateCharacterId(id: string): string | null {
  if (!id) return '이름(id)을 입력하세요'
  return CID_RE.test(id) ? null : CID_RULE
}

/** "My Hero.png" -> "my-hero" */
export function slugify(filename: string): string {
  const stem = filename.replace(/\.[^.]+$/, '')
  return stem.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40).replace(/-+$/, '')
}

/** Appends -2, -3, ... until the id is free. */
export function uniqueId(slug: string, taken: string[]): string {
  if (!slug || !taken.includes(slug)) return slug
  for (let n = 2; ; n++) {
    const suffix = `-${n}`
    const candidate = slug.slice(0, 40 - suffix.length) + suffix
    if (!taken.includes(candidate)) return candidate
  }
}

export const VIEW_OPTIONS = [
  { value: 'side', label: 'side (횡스크롤)' },
  { value: 'topdown', label: 'topdown (탑다운)' },
  { value: '3/4', label: '3/4' },
  { value: 'front', label: 'front (정면)' },
  { value: 'rear', label: 'rear (후면)' },
] as const

export const ART_STYLE_OPTIONS = [
  { value: 'project_native', label: 'project_native (기본)' },
  { value: 'auto', label: 'auto' },
  { value: 'pixel_art', label: 'pixel_art' },
  { value: 'retro_pixel', label: 'retro_pixel' },
  { value: 'pixel_inspired', label: 'pixel_inspired' },
  { value: 'clean_hd', label: 'clean_hd' },
] as const
