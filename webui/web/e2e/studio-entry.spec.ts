import { expect, test } from './fixtures'

// A character whose every unit is accepted used to have no way back into the studio: its dashboard card goes
// straight to export. These three entry points must reach a working studio for such a character.
test('a fully accepted character can be opened in the studio from the dashboard and the export page', async ({ page, server }) => {
  await server.start()
  await server.seedCharacter('hero', 'npc')
  const { job } = await server.api('/api/characters/hero/generate-all', {
    method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ auto_accept: true }),
  })
  expect((await server.waitJob(job.id)).state).toBe('succeeded')
  const { status } = await server.api('/api/characters/hero')
  const units = status.units as { state: string }[]
  expect(units.length).toBeGreaterThan(0)
  expect(units.every((u) => u.state === 'accepted' || u.state === 'mirrored')).toBe(true)

  // dashboard: the card still leads to export, the extra button opens the studio
  await page.goto('/')
  await expect(page.getByTestId('character-card-hero')).toHaveAttribute('href', '/c/hero/export')
  await page.getByTestId('character-studio-hero').click()
  await expect(page.getByTestId('studio-page')).toBeVisible()
  await expect(page).toHaveURL(/\/c\/hero\/studio\//)
  // the studio is really usable for an accepted unit: its accepted attempt is shown and regenerating is enabled
  await expect(page.locator('[data-testid^="accepted-badge-"]').first()).toBeVisible()
  await expect(page.getByTestId('generate-button')).toBeEnabled()

  // export page link, shown although nothing is missing
  await page.goto('/c/hero/export')
  await expect(page.getByTestId('export-missing-alert')).toHaveCount(0)
  await page.getByTestId('export-studio-link').click()
  await expect(page.getByTestId('studio-page')).toBeVisible()
})
