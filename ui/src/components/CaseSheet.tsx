import { useRef } from 'react'
import { fmtMyr, type ApproveResult, type CaseFile, type RingComponents } from '../api'
import { useDialog } from '../hooks'

type Props = {
  open: boolean
  onClose: () => void
  caseFile: CaseFile | null
  components?: RingComponents
  modeLabel: string
  canApprove: boolean
  approving: boolean
  approved: boolean
  receipt: ApproveResult | null
  notices: string[]
  onApprove: () => void
  stopped: number
}

const SIGNALS: [keyof RingComponents, string, string][] = [
  ['flow_through', 'Pass-through', 'Money leaves almost as fast as it arrives'],
  ['cross_bank_span', 'Spans banks', 'Activity is spread across several banks'],
  ['temporal_compactness', 'Fast hops', 'Hops happen within a short window'],
  ['node_score', 'Account risk', 'How risky each account looks on its own'],
  ['inflow_anomaly', 'Unusual inflow', 'Sudden large deposits for these accounts'],
  ['link_density', 'Tight links', 'How tightly the accounts connect to each other'],
]

const pct = (n: number) => `${Math.round(n * 100)}%`

export function CaseSheet({
  open,
  onClose,
  caseFile,
  components,
  modeLabel,
  canApprove,
  approving,
  approved,
  receipt,
  notices,
  onApprove,
  stopped,
}: Props) {
  const ref = useRef<HTMLElement>(null)
  useDialog(open, onClose, ref)

  const plan = caseFile?.freeze_priority ?? []
  const banks = [...new Set(plan.map((f) => f.bank))].sort()
  const worst = plan.reduce((m, f) => Math.max(m, f.false_freeze_risk), 0)
  const template = (caseFile?.mode ?? '').toLowerCase().includes('template') || modeLabel === 'TEMPLATE'

  return (
    <aside
      ref={ref}
      className={`sheet ${open ? 'open' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="case-title"
      inert={!open}
    >
      <div className="sheet-top">
        <div>
          <p className="kicker">Case file for analyst review</p>
          <h3 id="case-title">{caseFile?.headline ?? 'Case'}</h3>
          <p className="meta">
            {caseFile?.risk_level ?? '—'} risk · {caseFile?.confidence ?? '—'} confidence · analyst
            decision required
          </p>
        </div>
        <span
          className="pill"
          title={
            template
              ? 'Written from a fixed template with no AI call. With a Gemini key the case is AI-drafted, validated against the same evidence, and falls back to this template on failure.'
              : 'Case file mode'
          }
        >
          {modeLabel}
        </span>
      </div>

      <div className="sheet-mid">
        <div>
          <div className="decision-box">
            <b>Decision needed</b>
            <span>
              Hold {plan.length} account{plan.length === 1 ? '' : 's'}
              {banks.length ? ` at Bank${banks.length > 1 ? 's' : ''} ${banks.join(' and ')}` : ''}. Chance
              that any one of them is innocent: up to {pct(worst)}. Nothing is frozen until you approve.
            </span>
          </div>

          <h4>Why this looks like a ring</h4>
          <ul>
            {(caseFile?.why_suspicious ?? []).map((w) => (
              <li key={w.claim}>{w.claim}</li>
            ))}
          </ul>

          {components && (
            <>
              <h4 className="gap">Signal strength (0–100%)</h4>
              <ul className="bars">
                {SIGNALS.filter(([k]) => components[k] != null).map(([k, label, hint]) => (
                  <li key={k} title={hint}>
                    <span className="bar-label">{label}</span>
                    <span className="bar" aria-hidden>
                      <i style={{ width: pct(components[k] ?? 0) }} />
                    </span>
                    <span className="bar-val">{pct(components[k] ?? 0)}</span>
                    <span className="bar-hint">{hint}</span>
                  </li>
                ))}
              </ul>
            </>
          )}

          <h4 className="gap">Money trail</h4>
          <p className="fine">ACC-nn are case-file aliases. The investigator never sees real account numbers.</p>
          <ul>
            {(caseFile?.money_trail ?? []).slice(0, 7).map((h, i) => (
              <li key={`${h.from_alias}-${i}`}>
                {h.from_alias} → {h.to_alias}
                <span>{fmtMyr(h.amount_myr)}</span>
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h4>Recommended freeze order</h4>
          <ol>
            {plan.map((f) => (
              <li key={f.alias}>
                {f.rank}. {f.alias} · Bank {f.bank} · {f.tier}
                <span>
                  Expected stop {fmtMyr(f.expected_stopped_myr)} · {pct(f.false_freeze_risk)} chance this
                  account is innocent
                </span>
              </li>
            ))}
          </ol>
          <p className="fine">
            T4 = strongest evidence (several independent signals). Look-alike profiles are capped at T2
            unless a strong device link exists.
          </p>

          {(caseFile?.counter_evidence?.length ?? 0) > 0 && (
            <>
              <h4 className="gap">Counter-evidence</h4>
              <ul>
                {(caseFile?.counter_evidence ?? []).map((c) => (
                  <li key={c.claim}>{c.claim}</li>
                ))}
              </ul>
            </>
          )}

          {(caseFile?.signal_sensitivity?.length ?? 0) > 0 && (
            <>
              <h4 className="gap">What if a signal is wrong?</h4>
              <p className="fine">
                Ring score with one signal removed. A big drop means the case leans on that signal.
              </p>
              <ul>
                {(caseFile?.signal_sensitivity ?? []).map((s) => (
                  <li key={s.signal}>
                    Without {s.signal.replace(/_/g, ' ')}
                    <span>
                      score {s.score_without.toFixed(2)} ({s.delta >= 0 ? '−' : '+'}
                      {Math.abs(s.delta).toFixed(2)})
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}

          {approved && (
            <div className="receipt" role="status">
              <b>Approved · decision logged</b>
              <span>
                {receipt?.recorded
                  ? 'RECORDED mode: simulated locally, nothing was written to a hub.'
                  : receipt?.decision?.hash
                    ? `Chain hash ${receipt.decision.hash.slice(0, 16)}…`
                    : 'Decision recorded.'}{' '}
                {stopped > 0 ? `${fmtMyr(stopped)} stopped so far.` : 'The freeze lands shortly in the replay.'}
              </span>
              {notices.length > 0 && (
                <ul>
                  {notices.map((n) => (
                    <li key={n.slice(0, 40)}>{n}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="sheet-bot">
        <p className="bot-note">
          {approved
            ? 'Banks apply the holds. You can close this panel; the replay continues.'
            : canApprove
              ? 'The hub recommends. A human decides.'
              : 'Approval unlocks when the hub raises an alert.'}
        </p>
        <button type="button" className="btn ghost" onClick={onClose} data-autofocus={approved || undefined}>
          {approved ? 'Back to the replay' : 'Close'}
        </button>
        {!approved && (
          <button
            type="button"
            className="btn solid"
            onClick={onApprove}
            disabled={!canApprove || approving}
            aria-busy={approving}
          >
            {approving ? 'Approving…' : 'Approve freeze (analyst)'}
          </button>
        )}
      </div>
    </aside>
  )
}
