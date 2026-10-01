import { test as base, expect } from '@playwright/test'
import { execFileSync, spawn, type ChildProcess } from 'node:child_process'
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { FAKE_CODEX, REFERENCE_PNG, REPO_ROOT } from './paths'

export { expect }

export interface Server {
  url: string
  /** (re)starts `uv run sprite-forge-web` on the same port and root; FAKE_CODEX_MODE defaults to success */
  start(mode?: string, env?: Record<string, string>): Promise<void>
  /** SIGKILL of the server, its process group and every descendant (fake codex children) (a crash, no graceful shutdown) */
  kill(): Promise<void>
  /** setup / observation helpers that talk to the API directly (never used for the asserted UI flow) */
  api(path: string, init?: RequestInit): Promise<any>
  /** creates a character with the reference image, an analyzed identity and a plan for `bundle` */
  seedCharacter(id: string, bundle: string, view?: 'side' | 'topdown', set?: string[]): Promise<void>
  waitJob(jobId: string): Promise<any>
}

/** pid and all its descendants; the server starts each codex in its own session, so a process-group kill misses them */
function descendants(pid: number): number[] {
  const rows = execFileSync('ps', ['-A', '-o', 'pid=,ppid='], { encoding: 'utf8' }).trim().split('\n').map((l) => l.trim().split(/\s+/).map(Number))
  const found = [pid]
  for (const p of found) for (const [child, parent] of rows) if (parent === p && !found.includes(child)) found.push(child)
  return found
}

const freePort = () =>
  new Promise<number>((resolve, reject) => {
    const s = createServer().once('error', reject).listen(0, '127.0.0.1', () => {
      const { port } = s.address() as { port: number }
      s.close(() => resolve(port))
    })
  })

async function waitUp(url: string, child: ChildProcess) {
  for (let i = 0; i < 300; i++) {
    if (child.exitCode !== null) throw new Error(`sprite-forge-web exited early (${child.exitCode})`)
    try {
      if ((await fetch(`${url}/api/presets`)).ok) return
    } catch { /* not listening yet */ }
    await new Promise((r) => setTimeout(r, 100))
  }
  throw new Error('sprite-forge-web did not start')
}

export const test = base.extend<{ server: Server }>({
  server: async ({}, use) => {
    const tmp = mkdtempSync(join(tmpdir(), 'sprite-forge-e2e-'))
    const root = join(tmp, 'sprites')
    const codexHome = join(tmp, 'codex-home')
    mkdirSync(codexHome)
    const port = await freePort()
    const url = `http://127.0.0.1:${port}`
    let child: ChildProcess | undefined

    const kill = async () => {
      if (!child || child.exitCode !== null) return
      const exited = new Promise((r) => child!.once('exit', r))
      const pids = descendants(child.pid!)
      process.kill(-child.pid!, 'SIGKILL')
      for (const pid of pids) try { process.kill(pid, 'SIGKILL') } catch { /* already gone */ }
      await exited
    }
    const api = async (path: string, init?: RequestInit) => {
      const r = await fetch(`${url}${path}`, init)
      if (!r.ok) throw new Error(`${init?.method ?? 'GET'} ${path} -> ${r.status} ${await r.text()}`)
      return r.json()
    }
    const post = (path: string, body?: unknown) =>
      api(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body ?? {}) })
    const waitJob = async (jobId: string) => {
      for (let i = 0; i < 600; i++) {
        const { job } = await api(`/api/jobs/${jobId}`)
        if (!['queued', 'running'].includes(job.state)) return job
        await new Promise((r) => setTimeout(r, 100))
      }
      throw new Error(`job ${jobId} did not finish`)
    }

    const server: Server = {
      url,
      api,
      waitJob,
      async start(mode = 'success', extraEnv = {}) {
        child = spawn('uv', ['run', 'sprite-forge-web', '--port', String(port), '--root', root], {
          cwd: REPO_ROOT,
          detached: true, // own process group so kill() also reaches the codex children
          stdio: 'ignore',
          env: {
            ...process.env,
            SPRITE_FORGE_CODEX_BIN: FAKE_CODEX,
            CODEX_HOME: codexHome,
            FAKE_CODEX_DOCTOR: 'ok',
            FAKE_CODEX_MODE: mode,
            FAKE_CODEX_IMAGE: 'clean',
            // never pick up the developer's real video credentials; a test opts in with SPRITE_FORGE_VIDEO_PROVIDER=fake
            XAI_API_KEY: '',
            SPRITE_FORGE_GROK_AUTH: join(tmp, 'no-grok-auth.json'),
            SPRITE_FORGE_VIDEO_PROVIDER: '',
            ...extraEnv,
          },
        })
        await waitUp(url, child)
      },
      kill,
      async seedCharacter(id, bundle, view = 'side', set = []) {
        await post('/api/characters', { id, view, art_style: 'project_native', asset_type: 'character' })
        const form = new FormData()
        form.set('file', new Blob([readFileSync(REFERENCE_PNG)], { type: 'image/png' }), 'reference.png')
        await api(`/api/characters/${id}/reference`, { method: 'POST', body: form })
        const { job } = await post(`/api/characters/${id}/identity/analyze`)
        expect((await waitJob(job.id)).state).toBe('succeeded')
        await post(`/api/characters/${id}/plan`, view === 'topdown' ? { actions: [bundle], view, directions: ['down', 'up', 'right', 'left'], mirror: true, set } : { bundle, set })
      },
    }
    await use(server)
    await kill()
    rmSync(tmp, { recursive: true, force: true })
  },
  baseURL: async ({ server }, use) => use(server.url),
})
