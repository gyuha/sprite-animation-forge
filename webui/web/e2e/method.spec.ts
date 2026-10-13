import { expect, test } from './fixtures'

// generation method per action: `breathe` makes one still pose (1x1 sheet) and expands it into loop frames
test('a breathe idle is generated from one still, adopted, and plays as a multi-frame loop next to a grid walk', async ({ page, server }) => {
  await server.start()
  await server.seedCharacter('hero', 'npc', 'side', ['idle.method=breathe'])
  const plan = await server.api('/api/characters/hero/plan')
  expect(plan.plan.actions.idle).toMatchObject({ method: 'breathe', grid: '1x1', frames: 6 })
  expect(plan.plan.actions.walk.method).toBe('grid')

  const { job } = await server.api('/api/characters/hero/generate-all', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto_accept: true }),
  })
  expect((await server.waitJob(job.id)).state).toBe('succeeded')

  await page.goto('/c/hero/view')
  const idle = page.getByTestId('viewer-tile-idle')
  const walk = page.getByTestId('viewer-tile-walk')
  await expect(idle).toHaveAttribute('data-painted', 'true')
  await expect(idle).toHaveAttribute('data-frame-count', '6')
  await expect(walk).toHaveAttribute('data-painted', 'true')
  const frames = new Set<string | null>()
  for (let i = 0; i < 12; i++) {
    frames.add(await idle.getAttribute('data-frame'))
    await page.waitForTimeout(200)
  }
  expect(frames.size).toBeGreaterThan(1) // the breathing loop really advances

  // the plan screen shows the chosen method
  await page.goto('/c/hero/plan')
  await page.getByTestId('action-toggle-idle').click()
  await expect(page.getByTestId('action-method-idle')).toContainText('호흡')
  await expect(page.getByTestId('action-method-video-hint')).toBeVisible()
})
