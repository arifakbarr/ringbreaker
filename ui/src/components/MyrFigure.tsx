import { useEffect, useRef, useState } from 'react'

type Props = {
  label: string
  value: number
  tone?: 'loss' | 'gain' | 'plain'
  /** One plain-language line under the figure. */
  note?: string
}

/** Eases toward `target` so jumps read as movement; the number is real text, not canvas. */
function useTween(target: number, ms = 600) {
  const [shown, setShown] = useState(target)
  const from = useRef(target)
  const shownRef = useRef(target)

  useEffect(() => {
    from.current = shownRef.current
    const start = performance.now()
    let raf = 0
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / ms)
      const eased = 1 - Math.pow(1 - p, 3)
      const v = from.current + (target - from.current) * eased
      shownRef.current = v
      setShown(v)
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])

  return shown
}

/** Typographic MYR figure. */
export function MyrFigure({ label, value, tone = 'plain', note }: Props) {
  const cls = tone === 'loss' ? 'v loss' : tone === 'gain' ? 'v gain' : 'v'
  const shown = useTween(Math.round(value))
  return (
    <div className="figure">
      <span className="k">{label}</span>
      <span className={cls}>
        <span className="sr">RM {Math.round(value).toLocaleString('en-MY')}</span>
        <span className="cur" aria-hidden>
          RM
        </span>
        <span className="count" aria-hidden>
          {Math.round(shown).toLocaleString('en-US')}
        </span>
      </span>
      {note && <span className="note">{note}</span>}
    </div>
  )
}
