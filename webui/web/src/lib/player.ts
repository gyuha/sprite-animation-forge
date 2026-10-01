/** Pure playback helpers for AnimationPlayer (docs/09 5). */

/** One-shot actions rest on their last frame this long before the preview repeats. */
export const ONE_SHOT_HOLD_MS = 400

/** Frame index to show `t` ms after the start. Loop actions repeat; one-shot ones hold the last frame, then repeat. */
export function frameAt(t: number, fps: number, count: number, loop: boolean): number {
  if (count <= 1 || fps <= 0) return 0
  const frameMs = 1000 / fps
  const playMs = count * frameMs
  const cycle = loop ? playMs : playMs + ONE_SHOT_HOLD_MS
  const inCycle = ((t % cycle) + cycle) % cycle
  return Math.min(count - 1, Math.floor(inCycle / frameMs))
}

/** Start time (ms into the cycle) of `frame`: keeps the shown frame when fps changes or playback resumes. */
export const originFor = (frame: number, fps: number) => (frame * 1000) / fps

/** Frame step with wrap-around. */
export const stepFrame = (frame: number, delta: number, count: number) => (count <= 0 ? 0 : (((frame + delta) % count) + count) % count)

/** Bounding box [x0, y0, x1, y1) of pixels with alpha > 0 in RGBA data, or null for an empty image. */
export function alphaBBox(data: ArrayLike<number>, width: number, height: number): [number, number, number, number] | null {
  let x0 = width, y0 = height, x1 = -1, y1 = -1
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] > 0) {
        if (x < x0) x0 = x
        if (x > x1) x1 = x
        if (y < y0) y0 = y
        if (y > y1) y1 = y
      }
    }
  }
  return x1 < 0 ? null : [x0, y0, x1 + 1, y1 + 1]
}

/** Concatenated `?v=` hashes of the frame URLs: changes whenever any frame was rewritten (reprocess). */
export const framesVersion = (urls: string[]) => urls.map((u) => u.split('v=')[1] ?? '').join('.')
