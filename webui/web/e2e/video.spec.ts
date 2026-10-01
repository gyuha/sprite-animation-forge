import { execFileSync } from 'node:child_process'
import { expect, test } from './fixtures'

const hasFfmpeg = (() => {
  try { execFileSync('ffmpeg', ['-version'], { stdio: 'ignore' }); return true } catch { return false }
})()

// method=video with the fake video provider (no network): clip -> frames -> normal QC / adopt / viewer
test('a video idle is generated from a clip, shows its clip and prompt version, is adopted and plays in the viewer', async ({ page, server }) => {
  test.skip(!hasFfmpeg, 'ffmpeg is not installed')
  await server.start('success', { SPRITE_FORGE_VIDEO_PROVIDER: 'fake' })
  await server.seedCharacter('hero', 'npc', 'side', ['idle.method=video', 'idle.frames=6'])
  const plan = await server.api('/api/characters/hero/plan')
  expect(plan.plan.actions.idle).toMatchObject({ method: 'video', frames: 6 })
  const { job } = await server.api('/api/characters/hero/actions/idle/generate', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: '{}',
  })
  expect((await server.waitJob(job.id)).state).toBe('succeeded')

  await page.goto('/c/hero/studio/idle')
  await expect(page.getByTestId('attempt-prompt-version-001')).toHaveText('video_prompt@1')
  await expect(page.getByTestId('attempt-video-link')).toHaveAttribute('href', /raw\.mp4/)
  await page.getByTestId('accept-button').click()
  const confirm = page.getByTestId('accept-confirm')
  if (await confirm.isVisible().catch(() => false)) await confirm.click()
  await expect(page.getByTestId('accepted-badge-001')).toBeVisible()

  await page.goto('/c/hero/view')
  const idle = page.getByTestId('viewer-tile-idle')
  await expect(idle).toHaveAttribute('data-painted', 'true')
  await expect(idle).toHaveAttribute('data-frame-count', '6')
})
