export type Hero = {
  seed: number
  time_to_detect_s: number | null
  ring_alerted: boolean
  cashed_out_today_myr: number
  cashed_out_rb_myr: number
  stopped_myr: number
  false_freezes: number
  lookalike_full_freezes: number
  banks_spanned: string[]
  ring_id: string | null
  ring_score?: number
  planner_expected_myr?: number
  payee_p95_ms?: number
  meta?: { analyst_delay_s?: number; cash_out_complete_ts_today?: number | null }
}

export type ReplayEvent = {
  edge_id: string
  src: string
  dst: string
  src_bank: string
  dst_bank: string
  amount_myr: number
  ts: number
  channel: string
  is_ring: boolean
  victim_id: string | null
}

export type RingComponents = {
  node_score?: number
  flow_through?: number
  cross_bank_span?: number
  link_density?: number
  temporal_compactness?: number
  inflow_anomaly?: number
}

export type Replay = {
  seed: number
  live_window_end: number
  /** The world with Ringbreaker's freeze applied. */
  events: ReplayEvent[]
  /** The same seed with no intervention. Absent in packs recorded before this field existed. */
  today_events?: ReplayEvent[]
  hub_timeline?: { ts: number; event: string; score?: number; banks?: string[]; components?: RingComponents }[]
  today_outcomes?: Record<string, unknown>
  ringbreaker_outcomes?: Record<string, unknown>
  ground_truth_reveal?: { members?: Record<string, string[]>; lookalikes?: string[] }
}

export type CaseFile = {
  case_id: string
  headline: string
  mode: string
  risk_level?: string
  confidence?: string
  why_suspicious?: { claim: string; evidence_ids?: string[] }[]
  freeze_priority?: {
    rank: number
    alias: string
    bank: string
    tier: string
    expected_stopped_myr: number
    false_freeze_risk: number
  }[]
  counter_evidence?: { claim: string }[]
  money_trail?: { from_alias: string; to_alias: string; amount_myr: number }[]
  per_bank_notices?: Record<string, { body?: string; text?: string; text_ms?: string; bank?: string }>
  signal_sensitivity?: {
    signal: string
    score_without: number
    delta: number
    evidence_id?: string
  }[]
  feedback_applied?: string[]
}

export type PrivacySnapshot = {
  claim: string
  raw_fields_sent_total: number
  not_a_compliance_claim?: boolean
  ledgers?: Record<
    string,
    { messages_by_type?: Record<string, number>; tokens_sent?: number; raw_fields_sent?: number }
  >
}

export type Stat = { mean: number; ci95_low: number; ci95_high: number; n: number }

export type Proof = {
  available?: boolean
  generated_at?: string | null
  config_hash?: string | null
  scoreboard?: {
    seeds: number[]
    alert_rate: number | null
    time_to_detect_s: Stat | null
    stopped_myr: Stat | null
    false_freezes: Stat | null
  }
  network_effect?: { banks: string; alert_rate: number | null; stopped_myr: Stat | null; n: number }[]
  evasion?: {
    level: string
    alert_rate: number | null
    stopped_myr: Stat | null
    time_to_detect_s: Stat | null
    n: number
  }[]
  baseline?: {
    seeds: number[]
    local_only_ring_alert_rate: number | null
    local_only_mean_cashed_out_myr: number | null
    federated_ring_alert_rate: number | null
    federated_mean_stopped_myr: number | null
    n: number | null
  }
}

export type VictimWarning = {
  tier: number
  lang: string
  text: string
  synthetic?: boolean
  mode?: string
}

export type DataMode = 'LIVE' | 'RECORDED'

export type DemoBundle = {
  mode: DataMode
  hero: Hero
  replay: Replay
  caseFile: CaseFile
}

const LIVE_TIMEOUT_MS = 3000

function forceRecorded(): boolean {
  const q = new URLSearchParams(window.location.search)
  return q.get('mode')?.toUpperCase() === 'RECORDED' || q.get('recorded') === '1'
}

async function fetchJsonTimeout<T>(path: string, ms = LIVE_TIMEOUT_MS): Promise<T> {
  const ctrl = new AbortController()
  const timer = window.setTimeout(() => ctrl.abort(), ms)
  try {
    const r = await fetch(path, { signal: ctrl.signal })
    if (!r.ok) throw new Error(`${path} ${r.status}`)
    return (await r.json()) as T
  } finally {
    window.clearTimeout(timer)
  }
}

async function loadRecordedPack(): Promise<DemoBundle> {
  const pack = await fetchJsonTimeout<{
    cases?: CaseFile[]
    replay?: Replay
    hero_metrics?: Hero
  }>('/recorded/demo_pack.json', 8000)
  const caseFile = pack.cases?.[0]
  const hero = pack.hero_metrics
  const replay = pack.replay
  if (!caseFile || !hero || !replay) throw new Error('recorded pack incomplete')
  return {
    mode: 'RECORDED',
    hero,
    replay,
    caseFile: { ...caseFile, mode: caseFile.mode || 'RECORDED' },
  }
}

async function loadLive(): Promise<DemoBundle> {
  const [hWrap, replay, list] = await Promise.all([
    fetchJsonTimeout<{ hero: Hero }>('/v1/hero'),
    fetchJsonTimeout<Replay>('/v1/replay'),
    fetchJsonTimeout<{ cases: { case_id: string }[] }>('/cases'),
  ])
  const id = list.cases?.[0]?.case_id
  if (!id) throw new Error('no case')
  const caseFile = await fetchJsonTimeout<CaseFile>(`/cases/${id}`)
  return { mode: 'LIVE', hero: hWrap.hero, replay, caseFile }
}

export async function loadDemo(): Promise<DemoBundle> {
  if (forceRecorded()) return loadRecordedPack()
  try {
    return await loadLive()
  } catch {
    return loadRecordedPack()
  }
}

export type ApproveResult = {
  notices?: Record<string, { body?: string; text?: string; title?: string }>
  decision?: { decision_id?: string; hash?: string }
  note?: string
  recorded?: boolean
}

export async function approveCase(caseId: string, mode: DataMode): Promise<ApproveResult> {
  if (mode === 'RECORDED') {
    return {
      recorded: true,
      note: 'RECORDED mode — decision simulated locally (no hub write).',
      notices: {
        A: { title: 'Bank A', body: 'Simulated freeze notice (RECORDED). Analyst approval logged locally only.' },
        B: { title: 'Bank B', body: 'Simulated freeze notice (RECORDED).' },
        C: { title: 'Bank C', body: 'Simulated freeze notice (RECORDED).' },
      },
    }
  }
  const r = await fetch(`/cases/${caseId}/decision`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ analyst_id: 'demo-analyst', accounts: [] }),
  })
  if (!r.ok) throw new Error(`The hub rejected the decision (${r.status}). Nothing was frozen.`)
  return r.json()
}

export async function loadPrivacy(): Promise<PrivacySnapshot> {
  try {
    return await fetchJsonTimeout<PrivacySnapshot>('/v1/privacy')
  } catch {
    return {
      claim: 'privacy by design on pseudonymised data',
      raw_fields_sent_total: 0,
      not_a_compliance_claim: true,
    }
  }
}

export async function loadProof(): Promise<Proof> {
  for (const path of ['/v1/proof', '/recorded/proof.json']) {
    try {
      const p = await fetchJsonTimeout<Proof>(path)
      if (p.scoreboard) return p
    } catch {
      /* try the next source */
    }
  }
  return { available: false }
}

export async function loadVictimWarning(tier = 3, lang: 'en' | 'ms' = 'en'): Promise<VictimWarning> {
  try {
    return await fetchJsonTimeout<VictimWarning>(`/v1/warnings/victim?tier=${tier}&lang=${lang}`)
  } catch {
    // Baked EN/MS copy — same as server templates (offline RECORDED)
    const text =
      lang === 'ms'
        ? 'Sila jedakan pembayaran ini. Semakan penipuan (simulasi) menunjukkan risiko tinggi untuk penerima ini. Hubungi bank anda melalui nombor rasmi sebelum meneruskan. Jangan pindahkan wang ke akaun selamat lain.'
        : 'Please pause this payment. Our fraud check flagged elevated risk for this payee in a synthetic simulation. Contact your bank using its official number before continuing. Do not move money to another safe account.'
    return { tier, lang, text, synthetic: true, mode: 'RECORDED' }
  }
}

export function fmtMyr(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  return `RM ${n.toLocaleString('en-MY', { maximumFractionDigits: 0 })}`
}

export function fmtT(seconds: number) {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `T+${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
