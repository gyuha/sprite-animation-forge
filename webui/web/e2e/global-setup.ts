import { execFileSync } from 'node:child_process'
import { mkdirSync } from 'node:fs'
import { REFERENCE_PNG, REPO_ROOT, WEB_ROOT } from './paths'
import { dirname } from 'node:path'

/** Builds the production bundle the server serves and writes the reference image the tests upload. */
export default function globalSetup() {
  execFileSync('pnpm', ['build'], { cwd: WEB_ROOT, stdio: 'inherit' })
  mkdirSync(dirname(REFERENCE_PNG), { recursive: true })
  execFileSync('uv', ['run', 'python', 'webui/web/e2e/make_reference.py', REFERENCE_PNG], { cwd: REPO_ROOT, stdio: 'inherit' })
}
