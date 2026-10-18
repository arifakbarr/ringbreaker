import { useMemo } from 'react'
import { fmtMyr } from '../api'
import type { RiverRow } from '../model'

type Props = {
  rows: RiverRow[]
  emphasizeRing?: boolean
  label: string
}

export function River({ rows, emphasizeRing, label }: Props) {
  const shown = useMemo(() => rows.slice(-11).reverse(), [rows])

  return (
    <div className="river" role="log" aria-label={label}>
      {shown.map((e) => {
        const exit = e.channel === 'cash_out_exit'
        const cls = ['row']
        if (emphasizeRing && e.is_ring) cls.push('hot')
        if (exit && !e.held) cls.push('exit')
        if (e.held) cls.push('held')
        return (
          <div key={`${e.edge_id}${e.held ? '-held' : ''}`} className={cls.join(' ')}>
            <span className="when">{clock(e.ts)}</span>
            <span className="who">
              {short(e.src)}
              <em>→</em>
              {short(e.dst)}
              {e.held && <b className="tag">held</b>}
              {exit && !e.held && <b className="tag out">cash out</b>}
            </span>
            <span className="sum">{fmtMyr(e.amount_myr)}</span>
          </div>
        )
      })}
      {shown.length === 0 && (
        <div className="row">
          <span className="when">00:00</span>
          <span className="who">The window opens</span>
          <span className="sum">—</span>
        </div>
      )}
    </div>
  )
}

function short(id: string) {
  if (id.startsWith('EXT')) return 'cash exit'
  return `${id.slice(0, 3)}···${id.slice(-2)}`
}

function clock(ts: number) {
  const m = Math.floor(ts / 60)
  const s = Math.floor(ts % 60)
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
