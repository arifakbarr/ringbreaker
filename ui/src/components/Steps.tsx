import { STEPS, type Phase } from '../model'

type Props = {
  phase: Phase
  /** Show the review call-to-action while the alert is waiting for an analyst. */
  awaiting: boolean
  onReview: () => void
}

export function Steps({ phase, awaiting, onReview }: Props) {
  return (
    <section className="story" aria-label="What is happening">
      <ol className="steps">
        {STEPS.map((s, i) => {
          const state = i < phase.index ? 'done' : i === phase.index ? 'now' : 'next'
          return (
            <li key={s.id} className={state} aria-current={state === 'now' ? 'step' : undefined}>
              <span className="n">{state === 'done' ? '✓' : i + 1}</span>
              <span className="t">{s.title}</span>
              <span className="p">{s.plain}</span>
            </li>
          )
        })}
      </ol>
      <div className="narration" aria-live="polite">
        <p>{phase.text}</p>
        {awaiting && (
          <button type="button" className="btn solid" onClick={onReview}>
            Review case file
          </button>
        )}
      </div>
    </section>
  )
}
