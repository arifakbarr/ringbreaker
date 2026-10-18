import { fmtMyr, fmtT, type Hero, type Replay, type ReplayEvent } from './api'

/** Row shown in a river. `held` rows are transfers the freeze would have blocked. */
export type RiverRow = ReplayEvent & { held?: boolean }

export type Model = {
  /** What happens today: no hub. Falls back to the treated world for packs without `today_events`. */
  today: ReplayEvent[]
  /** The world after the analyst's freeze. */
  rb: ReplayEvent[]
  /** Ring transfers present today but absent once accounts are frozen. */
  blocked: ReplayEvent[]
  detectAt: number | null
  /** Sim time the freeze takes effect: alert + the analyst delay the simulator assumed. */
  freezeAt: number | null
  analystDelay: number
  /** Sim time the ring finished cashing out in today's world. */
  cashOutDoneAt: number | null
  /** Where the timeline rail ends (the 3 h window is mostly empty after cash-out). */
  end: number
  todayCashTotal: number
  blockedCashTotal: number
  hasTodayEvents: boolean
  first: ReplayEvent | null
  firstHopAt: number | null
  banks: string[]
}

const eventKey = (e: ReplayEvent) => `${e.src}|${e.dst}|${e.ts}|${e.amount_myr.toFixed(2)}`
const isCash = (e: ReplayEvent) => e.channel === 'cash_out_exit'
const sum = (xs: ReplayEvent[]) => xs.reduce((s, e) => s + e.amount_myr, 0)

export function buildModel(hero: Hero, replay: Replay): Model {
  const hasTodayEvents = !!replay.today_events?.length
  const today = hasTodayEvents ? replay.today_events! : replay.events
  const rb = replay.events
  const detectAt = hero.time_to_detect_s ?? null
  const analystDelay = hero.meta?.analyst_delay_s ?? 120
  const freezeAt = detectAt != null ? detectAt + analystDelay : null

  const rbKeys = new Set(rb.map(eventKey))
  const blocked =
    hasTodayEvents && freezeAt != null
      ? today.filter((e) => e.is_ring && e.ts > freezeAt && !rbKeys.has(eventKey(e)))
      : []

  const todayCash = today.filter(isCash)
  const lastCash = todayCash.length ? Math.max(...todayCash.map((e) => e.ts)) : null
  // `meta.cash_out_complete_ts_today` marks the first wave; the ring cashes out in waves, so use
  // the last exit to know when today's world has really lost everything.
  const cashOutDoneAt = lastCash ?? hero.meta?.cash_out_complete_ts_today ?? null
  const horizon = Math.max(cashOutDoneAt ?? 0, freezeAt ?? 0, detectAt ?? 0) + 600
  const end = Math.min(replay.live_window_end ?? 3600, Math.ceil(horizon / 60) * 60)

  const ring = today.filter((e) => e.is_ring)
  const first = ring.find((e) => e.victim_id) ?? ring[0] ?? null
  const hop = ring.find((e) => !e.victim_id && (!first || e.ts > first.ts))

  return {
    today,
    rb,
    blocked,
    detectAt,
    freezeAt,
    analystDelay,
    cashOutDoneAt,
    end: Math.max(end, 600),
    todayCashTotal: sum(todayCash),
    blockedCashTotal: sum(blocked.filter(isCash)),
    hasTodayEvents,
    first,
    firstHopAt: hop?.ts ?? null,
    banks: hero.banks_spanned?.length ? hero.banks_spanned : ['A', 'B', 'C'],
  }
}

export function cashedBy(events: ReplayEvent[], t: number) {
  let s = 0
  for (const e of events) if (isCash(e) && e.ts <= t) s += e.amount_myr
  return s
}

/** Money stopped so far: the hero total, released in step with the blocked cash-outs. */
export function stoppedBy(m: Model, hero: Hero, t: number, approved: boolean) {
  if (!approved || m.freezeAt == null || t < m.freezeAt) return 0
  if (m.blockedCashTotal <= 0) return t >= (m.cashOutDoneAt ?? m.freezeAt) ? hero.stopped_myr : 0
  const done = sum(m.blocked.filter((e) => isCash(e) && e.ts <= t))
  return hero.stopped_myr * Math.min(1, done / m.blockedCashTotal)
}

export function riverRows(m: Model, side: 'today' | 'rb', t: number, approved: boolean): RiverRow[] {
  if (side === 'today') return m.today.filter((e) => e.ts <= t)
  if (!approved) return m.today.filter((e) => e.ts <= t)
  const live: RiverRow[] = m.rb.filter((e) => e.ts <= t)
  const held: RiverRow[] = m.blocked.filter((e) => e.ts <= t).map((e) => ({ ...e, held: true }))
  return [...live, ...held].sort((a, b) => a.ts - b.ts)
}

export type StepId = 'scam' | 'chain' | 'alert' | 'analyst' | 'freeze'

export const STEPS: { id: StepId; title: string; plain: string }[] = [
  { id: 'scam', title: 'Scam payment', plain: 'A victim is tricked into paying a mule account.' },
  { id: 'chain', title: 'Money fans out', plain: 'It hops across banks. Each bank sees one hop.' },
  { id: 'alert', title: 'Hub sees the ring', plain: 'Anonymous tokens from all banks join into one chain.' },
  { id: 'analyst', title: 'Analyst approves', plain: 'A person reviews the case file and decides.' },
  { id: 'freeze', title: 'Accounts held', plain: 'Frozen accounts stop passing money on.' },
]

export type Phase = {
  step: StepId
  /** Steps strictly before this index are complete. */
  index: number
  text: string
}

export function phaseAt(m: Model, hero: Hero, t: number, approved: boolean, score: number | null): Phase {
  const detected = m.detectAt != null && t >= m.detectAt
  const banks = m.banks.join(', ')
  const stamp = (s: number) => fmtT(s)

  if (approved && m.freezeAt != null && t >= m.freezeAt) {
    const done = m.cashOutDoneAt != null && t >= m.cashOutDoneAt
    return {
      step: 'freeze',
      index: 4,
      text: done
        ? `${stamp(m.cashOutDoneAt!)} · Today, the ring has now cashed out ${fmtMyr(m.todayCashTotal)}. With the hub, ${fmtMyr(hero.stopped_myr)} was stopped (in our simulation).`
        : `Freeze is live since ${stamp(m.freezeAt)}. The ring can no longer pass the money on: blocked transfers show as “held” on the right while today’s world keeps cashing out on the left.`,
    }
  }
  if (approved) {
    return {
      step: 'analyst',
      index: 3,
      text: `Analyst approved. The simulation applies the freeze at ${stamp(m.freezeAt ?? t)} (alert plus an assumed ${Math.round(m.analystDelay / 60)}-minute analyst delay).`,
    }
  }
  if (detected) {
    const gone = m.cashOutDoneAt != null && t >= m.cashOutDoneAt
    return {
      step: 'analyst',
      index: 3,
      text: gone
        ? `No analyst decision, so nothing was frozen: the ring cashed out ${fmtMyr(m.todayCashTotal)} by ${stamp(m.cashOutDoneAt!)}. The hub never freezes on its own.`
        : `${stamp(m.detectAt!)} · The hub raises a ring alert${score != null ? ` (score ${score.toFixed(2)})` : ''} across Banks ${banks} and has drafted a case file. Nothing is frozen until an analyst approves.`,
    }
  }
  if (m.firstHopAt != null && t >= m.firstHopAt) {
    return {
      step: 'chain',
      index: 1,
      text: `Money now hops between Banks ${banks}. Each bank sees one hop of a normal-looking payment; no bank sees the chain.`,
    }
  }
  if (m.first && t >= m.first.ts) {
    return {
      step: 'scam',
      index: 0,
      text: `A victim at Bank ${m.first.src_bank} is tricked into sending ${fmtMyr(m.first.amount_myr)} to a mule account at Bank ${m.first.dst_bank}. To that bank it looks like an ordinary transfer.`,
    }
  }
  return { step: 'scam', index: 0, text: 'Replay ready. Press Play, or jump straight to the alert.' }
}
