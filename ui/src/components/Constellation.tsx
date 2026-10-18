import { useMemo } from 'react'
import type { ReplayEvent } from '../api'

type Props = {
  events: ReplayEvent[]
  t: number
  detected: boolean
  ringMembers: Set<string>
  freezing: boolean
}

type Pt = { id: string; bank: string; x: number; y: number }

export function Constellation({ events, t, detected, ringMembers, freezing }: Props) {
  const { nodes, arcs } = useMemo(() => {
    const visible = events.filter((e) => e.ts <= t && !e.src.startsWith('EXT') && !e.dst.startsWith('EXT'))
    const map = new Map<string, string>()
    for (const e of visible.slice(-160)) {
      map.set(e.src, e.src_bank)
      map.set(e.dst, e.dst_bank)
    }
    const ids = [...map.keys()]
    const ringIds = ids.filter((id) => ringMembers.has(id))
    const otherIds = ids.filter((id) => !ringMembers.has(id)).slice(0, 36)

    const nodes: Pt[] = []
    const cx = 300
    const cy = 210
    ringIds.slice(0, 14).forEach((id, i) => {
      const n = Math.max(ringIds.length, 1)
      const a = (i / n) * Math.PI * 2 - Math.PI / 2
      const r = 78 + (hash(id) % 28)
      nodes.push({
        id,
        bank: map.get(id) || 'A',
        x: cx + Math.cos(a) * r,
        y: cy + Math.sin(a) * r * 0.78,
      })
    })
    otherIds.forEach((id) => {
      const a = (hash(id) % 360) * (Math.PI / 180)
      const r = 150 + (hash(id + 'r') % 70)
      nodes.push({
        id,
        bank: map.get(id) || 'A',
        x: cx + Math.cos(a) * r * 0.95,
        y: cy + Math.sin(a) * r * 0.62,
      })
    })

    const byId = new Map(nodes.map((n) => [n.id, n]))
    const arcs = visible
      .filter((e) => e.ts > t - 140)
      .slice(-40)
      .flatMap((e) => {
        const a = byId.get(e.src)
        const b = byId.get(e.dst)
        if (!a || !b) return []
        return [{ e, a, b }]
      })

    return { nodes, arcs }
  }, [events, t, ringMembers])

  return (
    <div className="viewport constellation-wrap">
      <div className={`detect ${detected ? 'show' : ''}`}>Ring visible · human decides</div>
      <svg
        className="constellation"
        viewBox="0 0 600 420"
        role="img"
        aria-label={
          detected
            ? 'Account graph: the hub has linked the ring accounts across the banks'
            : 'Account graph: accounts and recent transfers, no ring identified yet'
        }
      >
        <circle className="halo" cx="300" cy="210" r="96" />
        <circle className="halo" cx="300" cy="210" r="132" />
        {arcs.map(({ e, a, b }) => {
          const mx = (a.x + b.x) / 2 + (a.y - b.y) * 0.12
          const my = (a.y + b.y) / 2 + (b.x - a.x) * 0.12
          const live = e.is_ring && e.ts > t - 90
          const held = freezing && e.is_ring
          return (
            <path
              key={e.edge_id}
              className={`arc${live ? ' live' : ''}${held ? ' held' : ''}`}
              d={`M ${a.x} ${a.y} Q ${mx} ${my} ${b.x} ${b.y}`}
            />
          )
        })}
        {nodes.map((n) => {
          const on = detected && ringMembers.has(n.id)
          const r = on ? 5.5 : 2.8
          const cls = on ? `node on bank${n.bank}` : 'node'
          return <circle key={n.id} className={cls} cx={n.x} cy={n.y} r={r} />
        })}
      </svg>
      <ul className="legend" aria-label="Legend">
        <li><i className="dot bankA" />Bank A</li>
        <li><i className="dot bankB" />Bank B</li>
        <li><i className="dot bankC" />Bank C</li>
        <li><i className="dot plain" />Other accounts</li>
        <li className="legend-note">
          {detected
            ? 'Large dots = ring accounts. Highlight uses the simulator’s known ring (demo only).'
            : 'Ring accounts light up once the hub raises its alert.'}
        </li>
      </ul>
    </div>
  )
}

function hash(s: string) {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 33 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}
