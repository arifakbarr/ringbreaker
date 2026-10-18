import { useRef } from 'react'
import { fmtMyr, fmtT, type Hero, type PrivacySnapshot, type Proof, type Stat } from '../api'
import { useDialog } from '../hooks'

export type GuideTab = 'what' | 'how' | 'proof' | 'limits' | 'keys'

const TABS: { id: GuideTab; label: string }[] = [
  { id: 'what', label: 'What we’re building' },
  { id: 'how', label: 'How it works' },
  { id: 'proof', label: 'Evidence' },
  { id: 'limits', label: 'Limits & honesty' },
  { id: 'keys', label: 'Controls' },
]

type Props = {
  open: boolean
  tab: GuideTab
  onTab: (t: GuideTab) => void
  onClose: () => void
  firstRun: boolean
  hero: Hero | null
  privacy: PrivacySnapshot | null
  proof: Proof | null
  modeLabel: string
}

export function GuidePanel({ open, tab, onTab, onClose, firstRun, hero, privacy, proof, modeLabel }: Props) {
  const ref = useRef<HTMLElement>(null)
  useDialog(open, onClose, ref)

  return (
    <aside
      ref={ref}
      className={`sheet guide ${open ? 'open' : ''}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="guide-title"
      inert={!open}
    >
      <div className="sheet-top">
        <div>
          <p className="kicker">Judges’ guide · synthetic data · simulation</p>
          <h3 id="guide-title">What is Ringbreaker?</h3>
        </div>
        <span className="pill">{modeLabel}</span>
      </div>

      <div className="guide-tabs" role="tablist" aria-label="Guide sections">
        {TABS.map((x) => (
          <button
            key={x.id}
            type="button"
            role="tab"
            id={`tab-${x.id}`}
            aria-selected={tab === x.id}
            aria-controls="guide-panel"
            className={tab === x.id ? 'on' : ''}
            onClick={() => onTab(x.id)}
          >
            {x.label}
          </button>
        ))}
      </div>

      <div className="guide-body" id="guide-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} tabIndex={0}>
        {tab === 'what' && <What hero={hero} />}
        {tab === 'how' && <How privacy={privacy} />}
        {tab === 'proof' && <Evidence hero={hero} proof={proof} />}
        {tab === 'limits' && <Limits />}
        {tab === 'keys' && <Keys />}
      </div>

      <div className="sheet-bot">
        {firstRun && tab !== 'proof' && (
          <button type="button" className="btn ghost" onClick={() => onTab('proof')}>
            See the evidence
          </button>
        )}
        <button type="button" className="btn solid" onClick={onClose} data-autofocus>
          {firstRun ? 'Start the replay' : 'Back to the replay'}
        </button>
      </div>
    </aside>
  )
}

function What({ hero }: { hero: Hero | null }) {
  return (
    <div className="guide-cols">
      <section>
        <h4>The problem</h4>
        <p>
          In an <strong>authorised push payment (APP) scam</strong> the victim is tricked into
          sending the money themselves. Scammers split it across <em>mule accounts</em> at several
          banks and cash out within minutes.
        </p>
        <p>
          Each bank sees one ordinary-looking transfer. <strong>Nobody sees the whole chain</strong>,
          and banks can’t simply pool customer data.
        </p>
        <h4>What we’re building</h4>
        <p>
          A neutral <strong>hub</strong> that joins what the banks see <em>without</em> seeing
          customers. Banks send one-way tokens instead of account numbers. The hub finds the ring
          across banks, drafts a plain-language case file, and a{' '}
          <strong>human analyst decides</strong> whether to hold accounts.
        </p>
      </section>
      <section>
        <h4>Read the screen</h4>
        <ul className="plain">
          <li>
            <b>Left, “Today”</b> — the same scam with no hub. The money is cashed out.
          </li>
          <li>
            <b>Right, “With Ringbreaker”</b> — the same events, same clock. The hub links the ring;
            after the analyst approves, the freeze blocks the remaining cash-out.
          </li>
          <li>
            <b>Timeline</b> — amber dot = hub alert, green dot = freeze lands, red dot = today’s
            cash-out completes.
          </li>
        </ul>
        <h4>Two moments in the golden hour</h4>
        <ul className="plain">
          <li>
            <b>Prevention</b> — a payee-risk lookup when a payment is made (deterministic,
            sub-millisecond in the simulator).
          </li>
          <li>
            <b>Interception</b> — ring graph, freeze planner, case file, human approval. This is the
            replay you’re watching.
          </li>
        </ul>
        {hero && (
          <p className="callout">
            This replay: alert at <b>{hero.time_to_detect_s != null ? fmtT(hero.time_to_detect_s) : '—'}</b>
            , <b>{fmtMyr(hero.stopped_myr)}</b> stopped of {fmtMyr(hero.cashed_out_today_myr)} that
            leaves today, {hero.false_freezes} false freezes. All in our simulation.
          </p>
        )}
      </section>
    </div>
  )
}

function How({ privacy }: { privacy: PrivacySnapshot | null }) {
  const tokens = Object.values(privacy?.ledgers ?? {}).reduce((s, l) => s + (l.tokens_sent ?? 0), 0)
  return (
    <div>
      <ol className="flow">
        <li>
          <b>1 · Banks score locally</b>
          <span>
            Each bank scores its own accounts and turns identifiers into one-way tokens with a key
            only the banks hold.
          </span>
          <em>Leaves the bank: tokens, beacons, edges. Never names or account numbers.</em>
        </li>
        <li>
          <b>2 · Hub joins the graph</b>
          <span>
            Tokens from Banks A, B and C are merged. Communities are scored on six signals (flow-through,
            cross-bank span, link density, timing, node risk, unusual inflow).
          </span>
          <em>The hub never holds the key, so it can’t reverse a token.</em>
        </li>
        <li>
          <b>3 · Planner picks what to hold</b>
          <span>
            Ranks accounts within a freeze budget and prices in the risk of freezing an innocent
            “lookalike” account. T4 = strongest evidence; lookalike-like profiles are capped lower.
          </span>
        </li>
        <li>
          <b>4 · Investigator writes the case</b>
          <span>
            Gemini (optional) or a fixed template drafts the case from aliased fields (ACC-01…). Output
            is validated; the template is the fallback.
          </span>
          <em>The model never sees raw identifiers.</em>
        </li>
        <li>
          <b>5 · Analyst approves</b>
          <span>
            Only an analyst decision triggers holds. Each decision is appended to a hash-chained log.
          </span>
          <em>The system recommends; it never freezes on its own.</em>
        </li>
      </ol>
      <p className="callout">
        In this replay the banks exchanged <b>{tokens.toLocaleString('en-MY')}</b> tokens and sent{' '}
        <b>{privacy?.raw_fields_sent_total ?? 0}</b> raw fields. “Privacy by design on pseudonymised
        data” is the claim; it is not a compliance claim.
      </p>
    </div>
  )
}

const EVASION: Record<string, string> = {
  E0: 'Baseline ring',
  E1: 'Slower hops',
  E2: 'Amounts split under RM 9,900',
  E3: 'Fewer shared devices / IPs',
  E4: 'Deeper chain + decoy payments',
}
const BANKS: Record<string, string> = { A: 'Bank A only', AB: 'Banks A + B', ABC: 'Banks A + B + C' }

function ci(s: Stat | null | undefined, fmt: (n: number) => string) {
  if (!s) return '—'
  return `95% CI ${fmt(s.ci95_low)} to ${fmt(s.ci95_high)}, n=${s.n}`
}
const secs = (n: number) => `${Math.round(n)} s`
const num2 = (n: number) => n.toFixed(2)

function Evidence({ hero, proof }: { hero: Hero | null; proof: Proof | null }) {
  const sb = proof?.scoreboard
  const base = proof?.baseline
  return (
    <div>
      {!sb && <p className="callout">Evidence numbers are not available (results/results.json not found).</p>}
      {sb && (
        <>
          <div className="stats">
            <div>
              <span className="k">Time to ring alert</span>
              <span className="v">{sb.time_to_detect_s ? `${Math.round(sb.time_to_detect_s.mean)} s` : '—'}</span>
              <span className="s">{ci(sb.time_to_detect_s, secs)}</span>
            </div>
            <div>
              <span className="k">Money stopped per ring</span>
              <span className="v">{sb.stopped_myr ? fmtMyr(sb.stopped_myr.mean) : '—'}</span>
              <span className="s">{ci(sb.stopped_myr, (n) => fmtMyr(n))}</span>
            </div>
            <div>
              <span className="k">False freezes per run</span>
              <span className="v">{sb.false_freezes ? sb.false_freezes.mean.toFixed(2) : '—'}</span>
              <span className="s">{ci(sb.false_freezes, num2)}</span>
            </div>
          </div>
          <p className="fine">
            Mean over {sb.seeds.length} untouched test seeds ({sb.seeds[0]}–{sb.seeds[sb.seeds.length - 1]}), one
            simulated ring of about RM 46,500 each. The replay on screen is seed {hero?.seed ?? '—'}.
          </p>
        </>
      )}

      {base && base.local_only_ring_alert_rate != null && (
        <>
          <h4>Why a shared hub?</h4>
          <table className="mini">
            <thead>
              <tr>
                <th>Setup</th>
                <th>Cross-bank ring alert</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Banks on their own</td>
                <td>{Math.round((base.local_only_ring_alert_rate ?? 0) * 100)}%</td>
                <td>
                  Individual accounts get flagged, but the ring is never connected. Mean cash-out{' '}
                  {fmtMyr(base.local_only_mean_cashed_out_myr)}.
                </td>
              </tr>
              <tr>
                <td>Tokens + hub graph</td>
                <td>{Math.round((base.federated_ring_alert_rate ?? 0) * 100)}%</td>
                <td>Ring alerted; mean stopped {fmtMyr(base.federated_mean_stopped_myr)}.</td>
              </tr>
            </tbody>
          </table>
          <p className="fine">Development seeds, n={base.n}.</p>
        </>
      )}

      {proof?.network_effect && proof.network_effect.length > 0 && (
        <>
          <h4>More banks, more stopped</h4>
          <table className="mini">
            <thead>
              <tr>
                <th>Participating</th>
                <th>Mean stopped</th>
                <th>n</th>
              </tr>
            </thead>
            <tbody>
              {proof.network_effect.map((r) => (
                <tr key={r.banks}>
                  <td>{BANKS[r.banks] ?? r.banks}</td>
                  <td>{r.stopped_myr ? fmtMyr(r.stopped_myr.mean) : '—'}</td>
                  <td>{r.n}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="fine">Very small n; read as direction, not magnitude.</p>
        </>
      )}

      {proof?.evasion && proof.evasion.length > 0 && (
        <>
          <h4>When the scammers adapt</h4>
          <table className="mini">
            <thead>
              <tr>
                <th>Tactic</th>
                <th>Mean stopped</th>
                <th>Alert at</th>
              </tr>
            </thead>
            <tbody>
              {proof.evasion.map((r) => (
                <tr key={r.level}>
                  <td>
                    {r.level} · {EVASION[r.level] ?? ''}
                  </td>
                  <td>{r.stopped_myr ? fmtMyr(r.stopped_myr.mean) : '—'}</td>
                  <td>{r.time_to_detect_s ? fmtT(r.time_to_detect_s.mean) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="fine">3 seeds per tactic. Some tactics lower the amount stopped or delay the alert.</p>
        </>
      )}

      {proof?.config_hash && (
        <p className="fine src">
          Source: results/results.json · config hash {proof.config_hash.slice(0, 12)}… · generated{' '}
          {proof.generated_at?.slice(0, 10)}. Numbers are copied from the harness, never typed by hand.
        </p>
      )}
    </div>
  )
}

function Limits() {
  return (
    <div className="guide-cols">
      <section>
        <h4>What we claim</h4>
        <ul className="plain">
          <li>
            <b>Privacy by design on pseudonymised data.</b> Not “anonymous”, not “GDPR/PDPA compliant”.
          </li>
          <li>A human analyst approves every freeze. The hub recommends; it never acts alone.</li>
          <li>All figures are from a seeded simulator, not predictions for real banks.</li>
        </ul>
        <h4>Known limits</h4>
        <ul className="plain">
          <li>
            Shared-key HMAC tokens are pseudonymised, not private set intersection. A colluding bank
            plus the hub could brute-force low-entropy identifiers. Production path: OPRF-based PSI,
            secure aggregation, a neutral operator, legal review.
          </li>
          <li>Lookalike accounts exist by design (~1.5%); false freezes are measured and reported.</li>
          <li>No real bank integrations. Banks D and E do not participate.</li>
        </ul>
      </section>
      <section>
        <h4>What this demo simplifies</h4>
        <ul className="plain">
          <li>
            <b>Approve</b> is a stand-in for the analyst’s decision. The simulation assumes the
            freeze lands 2 minutes after the alert.
          </li>
          <li>
            Ring accounts are highlighted from the simulator’s ground truth once the alert fires; the
            hub’s own output is the case file.
          </li>
          <li>
            “Today” is the same seed run with no intervention; “With Ringbreaker” is the same seed
            with the freeze applied.
          </li>
          <li>
            Case files use a fixed template unless a Gemini key is configured. RECORDED mode replays
            a baked pack when the live hub is unreachable.
          </li>
        </ul>
      </section>
    </div>
  )
}

function Keys() {
  const rows: [string, string][] = [
    ['Space', 'Play / pause'],
    ['2', 'Jump to the hub alert'],
    ['3', 'Open the case file'],
    ['R', 'Reset the replay'],
    ['C', 'Guided crack demo (autoplay at 30×)'],
    ['?', 'Open this guide'],
    ['Esc', 'Close a panel'],
  ]
  return (
    <div className="guide-cols">
      <section>
        <h4>Keyboard</h4>
        <table className="mini">
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}>
                <td>
                  <kbd>{k}</kbd>
                </td>
                <td>{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h4>URL options</h4>
        <table className="mini">
          <tbody>
            <tr>
              <td>
                <code>?crack=1</code>
              </td>
              <td>Autoplay to the alert, open the case, approve.</td>
            </tr>
            <tr>
              <td>
                <code>?mode=RECORDED</code>
              </td>
              <td>Use the baked pack (works offline).</td>
            </tr>
            <tr>
              <td>
                <code>?intro=0</code>
              </td>
              <td>Skip this guide on load.</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  )
}
