// ─── Source Resolver ──────────────────────────────────────────────────────────

export interface SourceHit {
  url: string
  server?: string
  name?: string
}

export interface SourceResult {
  status: 'ok' | 'error'
  message?: string
  url?: string
  urls?: SourceHit[]
  episodes?: { season?: number; num: number; url: string | null }[]
  found?: number
  total?: number
  log?: string[]
}

export interface SourceTestRequest {
  tmdb_id?: number
  media_type: 'movie' | 'tv'
  title?: string
  year?: number
  season?: number
  episode?: number
  tvdb_id?: number
}

// ─── Pipeline / Jobs ──────────────────────────────────────────────────────────

export type JobStatus = 'queued' | 'running' | 'completed' | 'error' | 'paused'
export type JobKind   = 'movie' | 'episode'

export interface PipelineJob {
  id: string
  title: string
  kind: JobKind
  season: number | null
  episode: number | null
  output_mode: 'strm' | 'hls-dl'
  status: JobStatus
  progress: number
  error: string | null
  hls_url: string | null
  save_path: string | null
  created_at: number
  updated_at: number
}

// ─── Activity ─────────────────────────────────────────────────────────────────

export interface GrabToken { title: string; token: string }

export interface ActivityEvent {
  ts: number
  kind: 'search' | 'grab' | 'job'
  title: string
  detail: string
  status: 'ok' | 'error' | ''
  ref: string
  results: string[]
  url: string
  grabs: GrabToken[]
}

// ─── Health ───────────────────────────────────────────────────────────────────

export interface HealthResult {
  status: 'ok' | 'warn' | 'error' | 'unknown'
  latency: number | null
  url: string
  message?: string
}

// ─── Config ───────────────────────────────────────────────────────────────────

export type Config = Record<string, unknown>

// ─── Fetch helpers ────────────────────────────────────────────────────────────

/** Thrown when the server returns 401. Let the caller / router guard handle redirect. */
export class UnauthorizedError extends Error {
  constructor() { super('Unauthorized'); this.name = 'UnauthorizedError' }
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: 'no-store' })
  if (r.status === 401) throw new UnauthorizedError()
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (r.status === 401) throw new UnauthorizedError()
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function authPost(path: string, body: unknown): Promise<{ status?: string; error?: string }> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({}))
  if (!r.ok && !data.error) data.error = `${r.status} ${r.statusText}`
  return data
}

async function postForm(path: string, form: Record<string, string>): Promise<void> {
  const body = new URLSearchParams(form)
  await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: body.toString(),
  })
}

// ─── Public API ───────────────────────────────────────────────────────────────

export interface AuthStatus { initialized: boolean; authenticated: boolean }
export const getAuthStatus   = ()  => fetch('/api/auth/status', { cache: 'no-store' }).then(r => r.json()) as Promise<AuthStatus>
export const authSetup       = (username: string, password: string) => authPost('/api/auth/setup', { username, password })
export const authLogin       = (username: string, password: string) => authPost('/api/auth/login', { username, password })
export const authLogout      = () => fetch('/api/auth/logout', { method: 'POST' })

export const getHealth       = ()  => get<Record<string, HealthResult>>('/api/health')
export const getConfig       = ()  => get<Config>('/api/config')
export const getPipeline     = ()  => get<PipelineJob[]>('/api/pipeline')
export const getActivity     = ()  => get<ActivityEvent[]>('/api/activity')
export const sourceTest      = (p: SourceTestRequest) => post<Record<string, SourceResult>>('/api/source-test', p)
export const testGrabber     = (p: SourceTestRequest) => post<{ status: string; count: number; results: string[] }>('/api/test-grabber', p)
export const testIndexer     = (p: SourceTestRequest) => post<{ status: string; count: number; results: string[]; url: string; key_required: boolean }>('/api/test-indexer', p)
export const torznabSearch   = (p: URLSearchParams)   => fetch('/torznab/api?' + p).then(r => r.text())
export const saveSettings    = (data: Record<string, unknown>) => post<{ status: string }>('/api/settings', data)

export async function jobAction(action: 'resume' | 'pause' | 'delete', id: string): Promise<void> {
  await postForm('/tasks/action', { action, hashes: id })
}

export async function bulkAction(action: 'resume_all' | 'pause_all' | 'clear_done'): Promise<void> {
  await postForm('/tasks/bulk', { action })
}

export async function manualGrab(token: string, outputMode: string): Promise<void> {
  await postForm('/api/manual-grab', { token, output_mode: outputMode })
}
