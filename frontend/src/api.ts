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
  episodes?: { num: number; url: string | null }[]
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

// ─── Config ───────────────────────────────────────────────────────────────────

export type Config = Record<string, unknown>

// ─── Fetch helpers ────────────────────────────────────────────────────────────

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: 'no-store' })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
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

export const getConfig       = ()  => get<Config>('/api/config')
export const getPipeline     = ()  => get<PipelineJob[]>('/api/pipeline')
export const getActivity     = ()  => get<ActivityEvent[]>('/api/activity')
export const sourceTest      = (p: SourceTestRequest) => post<Record<string, SourceResult>>('/api/source-test', p)
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
