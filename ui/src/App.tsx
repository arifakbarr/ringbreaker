import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  approveCase,
  fmtMyr,
  fmtT,
  loadDemo,
  loadPrivacy,
  loadProof,
  loadVictimWarning,
  type ApproveResult,
  type CaseFile,
  type DataMode,
  type Hero,
  type PrivacySnapshot,
  type Proof,
  type Replay,
  type VictimWarning,
} from './api'
import FadeContent from './bits/FadeContent'
import { CaseSheet } from './components/CaseSheet'
import { Constellation } from './components/Constellation'
import { GuidePanel, type GuideTab } from './components/GuidePanel'
import { MyrFigure } from './components/MyrFigure'
import { River } from './components/River'
import { Steps } from './components/Steps'
import { Wordmark } from './components/Wordmark'
import { buildModel, cashedBy, phaseAt, riverRows, stoppedBy } from './model'

const SPEEDS = [1, 4, 10, 30, 60] as const
const SEEN_KEY = 'ringbreaker.guide.seen'

function seenGuide() {
  try {
    return window.localStorage.getItem(SEEN_KEY) === '1'
  } catch {
    return false
  }
}
function markGuideSeen() {
  try {
    window.localStorage.setItem(SEEN_KEY, '1')
  } catch {
    /* private mode: the guide simply shows again next time */
  }
}

export default function App() {
  const [hero, setHero] = useState<Hero | null>(null)
  const [replay, setReplay] = useState<Replay | null>(null)
  const [caseFile, setCaseFile] = useState<CaseFile | null>(null)
  const [dataMode, setDataMode] = useState<DataMode>('LIVE')
  const [error, setError] = useState<string | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState<(typeof SPEEDS)[number]>(30)
  const [sheet, setSheet] = useState(false)
  const [guide, setGuide] = useState(false)
  const [guideTab, setGuideTab] = useState<GuideTab>('what')
  const [firstRun, setFirstRun] = useState(false)
  const [freezing, setFreezing] = useState(false)
  const [toast, setToast] = useState(false)
  const [approved, setApproved] = useState(false)
  const [approving, setApproving] = useState(false)
  const [receipt, setReceipt] = useState<ApproveResult | null>(null)
  const [notices, setNotices] = useState<string[]>([])
  const [warning, setWarning] = useState<VictimWarning | null>(null)
  const [warnLang, setWarnLang] = useState<'en' | 'ms'>('en')
  const [privacy, setPrivacy] = useState<PrivacySnapshot | null>(null)
  const [proof, setProof] = useState<Proof | null>(null)
  const [crack, setCrack] = useState(false)
  const [alertHit, setAlertHit] = useState(false)
  const [attempt, setAttempt] = useState(0)

  const tRef = useRef(0)
  const alertSeen = useRef(false)
  const approvedRef = useRef(false)
  const approvingRef = useRef(false)
  const crackStep = useRef(0)
  const timers = useRef<number[]>([])

  const model = useMemo(() => (hero && replay ? buildModel(hero, replay) : null), [hero, replay])
  const end = model?.end ?? 3600
  const detectAt = model?.detectAt ?? null
  const detected = detectAt != null && t >= detectAt

  const ringMembers = useMemo(() => {
    const m = replay?.ground_truth_reveal?.members
    if (!m) return new Set<string>()
    return new Set(Object.values(m).flat())
  }, [replay])

  const seek = useCallback((v: number) => {
    tRef.current = v
    setT(v)
  }, [])

  const later = useCallback((fn: () => void, ms: number) => {
    const id = window.setTimeout(fn, ms)
    timers.current.push(id)
  }, [])

  // ----- load -----
  useEffect(() => {
    let dead = false
    ;(async () => {
      try {
        const [bundle, priv, prf] = await Promise.all([loadDemo(), loadPrivacy(), loadProof()])
        if (dead) return
        setHero(bundle.hero)
        setReplay(bundle.replay)
        setCaseFile(bundle.caseFile)
        setDataMode(bundle.mode)
        setPrivacy(priv)
        setProof(prf)
        setError(null)
        setLoadFailed(false)
        const q = new URLSearchParams(window.location.search)
        const wantsCrack = q.get('crack') === '1' || q.get('demo') === 'crack'
        const skipIntro = q.get('intro') === '0' || wantsCrack
        const forceIntro = q.get('intro') === '1'
        if (wantsCrack) {
          setCrack(true)
          setSpeed(30)
          setPlaying(true)
        } else if (!skipIntro && (forceIntro || !seenGuide())) {
          setFirstRun(true)
          setGuide(true)
          setPlaying(false)
        }
      } catch (e) {
        if (dead) return
        setLoadFailed(true)
        setError(e instanceof Error ? e.message : String(e))
      }
    })()
    return () => {
      dead = true
    }
  }, [attempt])

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach((id) => window.clearTimeout(id))
  }, [])

  useEffect(() => {
    if (!detected) return
    let dead = false
    ;(async () => {
      const w = await loadVictimWarning(3, warnLang)
      if (!dead) setWarning(w)
    })()
    return () => {
      dead = true
    }
  }, [detected, warnLang])

  // ----- clock -----
  useEffect(() => {
    if (!playing || !model) return
    let raf = 0
    let prev = performance.now()
    const loop = (now: number) => {
      const dt = Math.min(0.25, (now - prev) / 1000)
      prev = now
      let next = tRef.current + dt * speed
      // Stop on the alert so nobody scrolls past the moment the hub speaks.
      if (!alertSeen.current && detectAt != null && tRef.current < detectAt && next >= detectAt) {
        alertSeen.current = true
        seek(detectAt)
        setAlertHit(true)
        setPlaying(false)
        return
      }
      if (next >= end) {
        seek(end)
        setPlaying(false)
        return
      }
      if (next < 0) next = 0
      seek(next)
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [playing, speed, model, end, detectAt, seek])

  // ----- actions -----
  const reset = useCallback(() => {
    timers.current.forEach((id) => window.clearTimeout(id))
    timers.current.length = 0
    seek(0)
    alertSeen.current = false
    approvedRef.current = false
    approvingRef.current = false
    crackStep.current = 0
    setAlertHit(false)
    setApproved(false)
    setApproving(false)
    setReceipt(null)
    setNotices([])
    setToast(false)
    setFreezing(false)
    setSheet(false)
    setError(null)
    setPlaying(true)
  }, [seek])

  const approve = useCallback(async () => {
    if (!caseFile || approvedRef.current || approvingRef.current) return
    approvingRef.current = true
    setApproving(true)
    setError(null)
    setFreezing(true)
    try {
      const res = await approveCase(caseFile.case_id, dataMode)
      const lines: string[] = []
      if (res.notices) {
        for (const [bank, n] of Object.entries(res.notices)) {
          lines.push(`Bank ${bank.replace(/^Bank /, '')}: ${n.body || n.text || ''}`)
        }
      }
      if (caseFile.per_bank_notices && lines.length === 0) {
        for (const [bank, n] of Object.entries(caseFile.per_bank_notices)) {
          lines.push(`Bank ${bank}: ${n.text || n.body || ''}`)
        }
      }
      approvedRef.current = true
      setNotices(lines)
      setReceipt(res)
      setApproved(true)
      setToast(true)
      setPlaying(true)
      later(() => setFreezing(false), 900)
      later(() => setToast(false), 9000)
    } catch (e) {
      setFreezing(false)
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      approvingRef.current = false
      setApproving(false)
    }
  }, [caseFile, dataMode, later])

  const jumpToAlert = useCallback(() => {
    if (detectAt == null) return
    alertSeen.current = true
    seek(detectAt)
    setAlertHit(true)
    setPlaying(false)
  }, [detectAt, seek])

  const togglePlay = useCallback(() => {
    if (tRef.current >= end) {
      reset()
      return
    }
    setPlaying((p) => !p)
  }, [end, reset])

  const startCrack = useCallback(() => {
    reset()
    setCrack(true)
    setSpeed(30)
  }, [reset])

  const closeGuide = useCallback(() => {
    setGuide(false)
    if (firstRun) {
      setFirstRun(false)
      markGuideSeen()
      setPlaying(true)
    }
  }, [firstRun])

  const openGuide = useCallback((tab: GuideTab = 'what') => {
    setGuideTab(tab)
    setGuide(true)
  }, [])

  // Crack demo: alert → open case → approve → close panel so the freeze is visible.
  useEffect(() => {
    if (!crack || !alertHit || crackStep.current !== 0) return
    crackStep.current = 1
    setSheet(true)
    later(() => {
      crackStep.current = 2
      void approve()
    }, 1600)
    later(() => setSheet(false), 4600)
  }, [crack, alertHit, approve, later])

  // ----- keyboard -----
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const el = e.target as HTMLElement | null
      const tag = el?.tagName
      if (tag === 'INPUT' && (el as HTMLInputElement).type !== 'range') return
      if (tag === 'TEXTAREA' || tag === 'SELECT') return
      if (sheet || guide) return
      const k = e.key
      if (k === ' ' && tag !== 'BUTTON' && tag !== 'A' && tag !== 'INPUT') {
        e.preventDefault()
        togglePlay()
      } else if (k === 'r' || k === 'R') reset()
      else if (k === '1') seek(0)
      else if (k === '2') jumpToAlert()
      else if (k === '3' && detected) setSheet(true)
      else if (k === 'c' || k === 'C') startCrack()
      else if (k === '?') openGuide('keys')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sheet, guide, detected, togglePlay, reset, seek, jumpToAlert, startCrack, openGuide])

  // ----- derived view state -----
  const todayRows = useMemo(() => (model ? riverRows(model, 'today', t, approved) : []), [model, t, approved])
  const rbRows = useMemo(() => (model ? riverRows(model, 'rb', t, approved) : []), [model, t, approved])
  const cashedToday = model ? cashedBy(model.today, t) : 0
  const cashedRb = model ? cashedBy(approved ? model.rb : model.today, t) : 0
  const stopped = model && hero ? stoppedBy(model, hero, t, approved) : 0
  const score = replay?.hub_timeline?.[0]?.score ?? null
  const phase = model && hero ? phaseAt(model, hero, t, approved, score) : null
  const goneToday = model?.cashOutDoneAt != null && t >= model.cashOutDoneAt
  const awaiting = detected && !approved && !goneToday

  const modeLabel = dataMode === 'RECORDED' ? 'RECORDED' : (caseFile?.mode || 'LIVE').toUpperCase()
  const pct = (s: number) => `${Math.min(100, (s / end) * 100)}%`
  const tokens = Object.values(privacy?.ledgers ?? {}).reduce((s, l) => s + (l.tokens_sent ?? 0), 0)
  const dialogOpen = sheet || guide

  const approveHint = !detected
    ? 'Unlocks when the hub raises its alert'
    : approved
      ? 'Approved'
      : 'Review the case, then approve'

  return (
    <div className="app">
      <div className="topbar">
        <div className="seal">
          Synthetic data · simulation
          <span className={`mode-tag ${dataMode === 'RECORDED' ? 'rec' : ''}`}>{modeLabel}</span>
        </div>
        <nav className="toplinks" aria-label="Help">
          <button type="button" className="btn ghost" onClick={() => openGuide('what')}>
            What is this?
          </button>
          <button type="button" className="btn ghost" onClick={() => openGuide('proof')}>
            Evidence
          </button>
          <button type="button" className="btn ghost" onClick={startCrack} disabled={!model}>
            Play guided demo
          </button>
        </nav>
      </div>

      <header className="mast">
        <div>
          <Wordmark />
          <FadeContent blur duration={1.1} delay={0.2} threshold={0.01}>
            <p className="deck">
              Scam money crosses several banks in minutes, and no single bank sees the whole chain.
              Same scam, replayed twice on one clock: <b>today</b>, and <b>with a shared hub</b> where
              a human still approves every freeze.
            </p>
          </FadeContent>
        </div>
        <div className="actions">
          <button type="button" className="btn quiet" onClick={reset} disabled={!model} data-focus-fallback>
            Reset
          </button>
          <button
            type="button"
            className="btn quiet"
            onClick={() => setSheet(true)}
            disabled={!caseFile || !detected}
            title={detected ? 'Open the case file' : 'The case file appears when the hub raises its alert'}
          >
            Case file
          </button>
          <button
            type="button"
            className="btn solid"
            onClick={() => setSheet(true)}
            disabled={!caseFile || !detected || approved}
            title={approveHint}
          >
            {approved ? 'Approved ✓' : 'Review & approve'}
          </button>
        </div>
      </header>

      {loadFailed && (
        <div className="banner err" role="alert">
          <span>Couldn’t load the replay ({error}). Check the hub is running, or try the recorded copy.</span>
          <span className="banner-actions">
            <button type="button" className="btn ghost" onClick={() => setAttempt((n) => n + 1)}>
              Retry
            </button>
            <a className="btn ghost" href="?mode=RECORDED">
              Use recorded copy
            </a>
          </span>
        </div>
      )}
      {!loadFailed && error && (
        <div className="banner err" role="alert">
          <span>{error}</span>
          <button type="button" className="btn ghost" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {phase && <Steps phase={phase} awaiting={awaiting} onReview={() => setSheet(true)} />}

      {detected && warning && (
        <aside className="victim-strip" aria-live="polite">
          <div
            className="victim-kicker"
            title="What the payer’s bank would show when someone tries to pay a payee the hub has flagged."
          >
            Prevention · payer warning (tier {warning.tier})
          </div>
          <p>{warning.text}</p>
          <div className="victim-langs" role="group" aria-label="Warning language">
            <button
              type="button"
              className={warnLang === 'en' ? 'on' : ''}
              aria-pressed={warnLang === 'en'}
              onClick={() => setWarnLang('en')}
            >
              EN
            </button>
            <button
              type="button"
              className={warnLang === 'ms' ? 'on' : ''}
              aria-pressed={warnLang === 'ms'}
              onClick={() => setWarnLang('ms')}
            >
              BM
            </button>
          </div>
        </aside>
      )}

      <FadeContent blur duration={1.2} delay={0.15} threshold={0.01} className="theater-fade">
        <section className="theater" aria-label="Split replay">
          <article className="half left">
            <div className="half-label">
              <div>
                <h2>Today</h2>
                <p className="sub">
                  Each bank sees only its own accounts. The money hops across banks and leaves as cash
                  before anyone connects the dots.
                </p>
              </div>
              <MyrFigure
                label="Cashed out"
                value={cashedToday}
                tone="loss"
                note={cashedToday > 0 ? 'Left the banking system as cash' : 'No cash-out yet'}
              />
            </div>
            <div className="viewport">
              {!model && <p className="empty" role="status">{loadFailed ? 'No replay loaded.' : 'Loading replay…'}</p>}
              {model && <River rows={todayRows} label="Transfers today" />}
            </div>
          </article>

          <div className="gutter" aria-hidden />

          <article className="half right">
            <div className="half-label">
              <div>
                <h2>With Ringbreaker</h2>
                <p className="sub">
                  Banks share anonymous tokens only. The hub joins the hops into one ring; after an
                  analyst approves, the accounts are held.
                </p>
              </div>
              <MyrFigure
                label="Stopped"
                value={stopped}
                tone="gain"
                note={
                  approved
                    ? cashedRb > 0
                      ? `Still cashed out ${fmtMyr(cashedRb)}`
                      : 'Nothing cashed out'
                    : detected
                      ? 'Awaiting analyst'
                      : 'No ring found yet'
                }
              />
            </div>
            <div className="viewport split">
              <Constellation
                events={approved && model ? model.rb : (model?.today ?? [])}
                t={t}
                detected={detected}
                ringMembers={ringMembers}
                freezing={freezing}
              />
              {model && <River rows={rbRows} emphasizeRing label="Transfers with Ringbreaker" />}
            </div>
          </article>
        </section>
      </FadeContent>


      <footer className="timeline" aria-label="Replay controls">
        <div className="time-read" aria-live="off">
          {fmtT(t)}
        </div>
        <div className="rail">
          {model && (
            <>
              {detectAt != null && (
                <span className="mark alert" style={{ left: pct(detectAt) }} title={`Hub alert ${fmtT(detectAt)}`}>
                  <i>Alert</i>
                </span>
              )}
              {model.freezeAt != null && (
                <span
                  className={`mark freeze ${approved ? 'on' : ''}`}
                  style={{ left: pct(model.freezeAt) }}
                  title={`Freeze lands ${fmtT(model.freezeAt)} if the analyst approves`}
                >
                  <i>Freeze</i>
                </span>
              )}
              {model.cashOutDoneAt != null && (
                <span
                  className="mark cash"
                  style={{ left: pct(model.cashOutDoneAt) }}
                  title={`Today’s cash-out completes ${fmtT(model.cashOutDoneAt)}`}
                >
                  <i>Cash-out done</i>
                </span>
              )}
            </>
          )}
          <input
            type="range"
            min={0}
            max={end}
            step={1}
            value={Math.min(t, end)}
            onChange={(e) => {
              const v = Number(e.target.value)
              setPlaying(false)
              if (detectAt != null && v >= detectAt) alertSeen.current = true
              seek(v)
            }}
            aria-label="Replay time"
            aria-valuetext={fmtT(t)}
            disabled={!model}
          />
        </div>
        <div className="transport">
          <button type="button" className="tbtn wide" onClick={togglePlay} disabled={!model}>
            {t >= end ? 'Replay' : playing ? 'Pause' : 'Play'}
          </button>
          <div className="speeds" role="group" aria-label="Playback speed">
            {SPEEDS.map((s) => (
              <button
                key={s}
                type="button"
                className={`tbtn ${speed === s ? 'on' : ''}`}
                aria-pressed={speed === s}
                onClick={() => setSpeed(s)}
              >
                {s}×
              </button>
            ))}
          </div>
          <button type="button" className="tbtn wide" onClick={jumpToAlert} disabled={!model || detectAt == null}>
            Jump to alert
          </button>
        </div>
      </footer>

      <div className="privacy-foot">
        <span>
          {privacy?.claim ?? 'privacy by design on pseudonymised data'} · {tokens.toLocaleString('en-MY')} tokens
          shared · raw fields sent {privacy?.raw_fields_sent_total ?? 0} · not a compliance claim
        </span>
        <span className="hints">
          <kbd>Space</kbd> play · <kbd>2</kbd> alert · <kbd>3</kbd> case · <kbd>R</kbd> reset · <kbd>?</kbd> help
        </span>
      </div>


      <div
        className={`sheet-bg ${dialogOpen ? 'open' : ''}`}
        onClick={() => (guide ? closeGuide() : setSheet(false))}
        role="presentation"
      />

      <CaseSheet
        open={sheet && !guide}
        onClose={() => setSheet(false)}
        caseFile={caseFile}
        components={replay?.hub_timeline?.[0]?.components}
        modeLabel={modeLabel}
        canApprove={detected}
        approving={approving}
        approved={approved}
        receipt={receipt}
        notices={notices}
        onApprove={() => void approve()}
        stopped={stopped}
      />

      <GuidePanel
        open={guide}
        tab={guideTab}
        onTab={setGuideTab}
        onClose={closeGuide}
        firstRun={firstRun}
        hero={hero}
        privacy={privacy}
        proof={proof}
        modeLabel={modeLabel}
      />

      <div className={`toast ${toast && !dialogOpen ? 'show' : ''}`} role="status">
        <div className="eyebrow">In our simulation</div>
        <div className="amount">
          RM <CountInline value={hero?.stopped_myr ?? 0} /> stopped
        </div>
        <div className="note">
          False freezes {hero?.false_freezes ?? 0} · lookalike full freezes {hero?.lookalike_full_freezes ?? 0}{' '}
          · analyst approved, not autonomous
          {dataMode === 'RECORDED' ? ' · RECORDED' : ''}
        </div>
        <button type="button" className="toast-link" onClick={() => openGuide('proof')}>
          See the evidence
        </button>
      </div>
    </div>
  )
}

function CountInline({ value }: { value: number }) {
  // Plain text: a spring count-up can rest one ringgit short of the real figure.
  return <>{Math.round(value).toLocaleString('en-US')}</>
}
