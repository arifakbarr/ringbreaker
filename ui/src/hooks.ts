import { useEffect, type RefObject } from 'react'

const FOCUSABLE =
  'button:not([disabled]), a[href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

/**
 * Modal behaviour for a dialog that stays mounted: moves focus in on open, keeps Tab inside,
 * closes on Escape and returns focus to the opener. Pair with `inert={!open}` on the element.
 */
export function useDialog(open: boolean, onClose: () => void, ref: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const el = ref.current
    if (!open || !el) return
    const opener = document.activeElement as HTMLElement | null
    const items = () =>
      [...el.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((n) => n.getClientRects().length > 0)

    const focusTimer = window.setTimeout(() => {
      ;(el.querySelector<HTMLElement>('[data-autofocus]') ?? items()[0])?.focus()
    }, 60)

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
        return
      }
      if (e.key !== 'Tab') return
      const list = items()
      if (!list.length) return
      const first = list[0]
      const last = list[list.length - 1]
      const active = document.activeElement
      if (!el.contains(active)) {
        e.preventDefault()
        first.focus()
      } else if (e.shiftKey && active === first) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(focusTimer)
      document.removeEventListener('keydown', onKey)
      // The opener can unmount while the dialog is open (e.g. a CTA hidden by approval).
      const target = opener?.isConnected ? opener : document.querySelector<HTMLElement>('[data-focus-fallback]')
      target?.focus?.()
    }
    // onClose is intentionally excluded: callers pass inline closures and focus must not reset.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, ref])
}
