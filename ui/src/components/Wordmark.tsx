import { motion } from 'motion/react'

/**
 * Ringbreaker modular alphabet — filled construction blocks, not a webfont.
 * Square geometry · one severed ring · draftsman’s ledger under the name.
 */
const glyphs: Record<string, { w: number; paths: string[] }> = {
  R: {
    w: 40,
    paths: [
      'M0 0 H10 V56 H0 Z',
      'M10 0 H28 C40 0 40 16 28 16 H10 Z',
      'M18 16 L40 56 H28 L10 16 Z',
    ],
  },
  I: {
    w: 26,
    paths: [
      'M0 0 H26 V8 H0 Z',
      'M8 8 H18 V48 H8 Z',
      'M0 48 H26 V56 H0 Z',
    ],
  },
  N: {
    w: 40,
    paths: [
      'M0 0 H10 V56 H0 Z',
      'M30 0 H40 V56 H30 Z',
      'M10 0 L30 40 V56 L10 16 Z',
    ],
  },
  G: {
    w: 42,
    paths: [
      'M42 12 C42 0 32 0 21 0 C6 0 0 12 0 28 C0 44 6 56 21 56 C34 56 42 46 42 34 H32 C32 42 28 48 21 48 C12 48 10 40 10 28 C10 16 12 8 21 8 C28 8 32 12 32 18 H21 V28 H42 Z',
    ],
  },
  B: {
    w: 40,
    paths: [
      'M0 0 H10 V56 H0 Z',
      'M10 0 H25 C37 0 37 14 25 14 H10 Z',
      'M10 26 H27 C39 26 39 56 27 56 H10 Z',
    ],
  },
  E: {
    w: 36,
    paths: [
      'M0 0 H10 V56 H0 Z',
      'M10 0 H36 V8 H10 Z',
      'M10 24 H28 V32 H10 Z',
      'M10 48 H36 V56 H10 Z',
    ],
  },
  A: {
    w: 40,
    paths: [
      'M0 56 L15 0 H25 L40 56 H28 L24 40 H16 L12 56 Z',
      'M17 32 H23 L20 20 Z',
    ],
  },
  K: {
    w: 40,
    paths: [
      'M0 0 H10 V56 H0 Z',
      'M10 28 L36 0 H40 L18 28 L40 56 H36 L10 28 Z',
    ],
  },
}

function Letter({ ch, x }: { ch: string; x: number }) {
  const g = glyphs[ch]
  if (!g) return null
  return (
    <g transform={`translate(${x},0)`}>
      {g.paths.map((d) => (
        <path key={d.slice(0, 24)} d={d} />
      ))}
    </g>
  )
}

function spell(word: string, startX: number, tracking: number) {
  let x = startX
  return word.split('').map((ch, i) => {
    const g = glyphs[ch]
    const node = <Letter key={`${word}-${i}-${ch}`} ch={ch} x={x} />
    x += (g?.w ?? 32) + tracking
    return node
  })
}

export function Wordmark() {
  return (
    <motion.svg
      className="wordmark-svg"
      viewBox="0 0 820 132"
      role="img"
      aria-label="Ringbreaker"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
    >
      {/* Vitruvian underdrawing */}
      <g className="wm-ghost" fill="none" stroke="currentColor">
        <circle cx="54" cy="58" r="52" strokeWidth="0.7" />
        <circle cx="54" cy="58" r="34" strokeWidth="0.55" strokeDasharray="2 3.5" />
        <path d="M54 6 V110 M2 58 H106" strokeWidth="0.5" />
        <path d="M54 58 L98 24" strokeWidth="0.5" />
      </g>

      {/* Broken ring seal */}
      <g transform="translate(10,14)">
        <circle cx="44" cy="44" r="38" fill="none" stroke="currentColor" strokeWidth="1.2" opacity="0.25" />
        <path
          d="M14 64 A34 34 0 1 1 76 18"
          fill="none"
          stroke="currentColor"
          strokeWidth="7"
          strokeLinecap="round"
        />
        <path d="M78 14 L94 0" fill="none" stroke="currentColor" strokeWidth="3.5" strokeLinecap="round" />
        <circle cx="44" cy="44" r="5.5" fill="currentColor" />
      </g>

      {/* RING */}
      <g className="wm-ink" fill="currentColor" transform="translate(120, 30)">
        {spell('RING', 0, 6)}
      </g>

      {/* Sever mark */}
      <g transform="translate(300, 30)" stroke="currentColor" fill="none">
        <path d="M0 6 V50" strokeWidth="1.4" strokeDasharray="2.5 3.5" opacity="0.45" />
        <path d="M-8 28 H8" strokeWidth="3" strokeLinecap="square" />
      </g>

      {/* BREAKER */}
      <g className="wm-ink" fill="currentColor" transform="translate(318, 30)" opacity="0.94">
        {spell('BREAKER', 0, 7)}
      </g>

      {/* Banker's ledger */}
      <g className="wm-ledger" stroke="currentColor" fill="none">
        <path d="M120 108 H800" strokeWidth="1.2" />
        {Array.from({ length: 30 }).map((_, i) => (
          <path
            key={i}
            d={`M${120 + i * 22.5} 108 v${i % 5 === 0 ? 12 : 5}`}
            strokeWidth={i % 5 === 0 ? 1.4 : 1}
          />
        ))}
      </g>
    </motion.svg>
  )
}
