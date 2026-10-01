import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

export const WEB_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
export const REPO_ROOT = resolve(WEB_ROOT, '../..')
export const FAKE_CODEX = resolve(REPO_ROOT, 'sprite-animation-forge/tests/fixtures/fake_codex/codex')
export const REFERENCE_PNG = resolve(WEB_ROOT, 'test-results/reference.png')
