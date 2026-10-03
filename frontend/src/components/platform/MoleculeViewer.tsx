import { useEffect, useRef, useState } from 'react'

declare global {
  interface Window {
    $3Dmol?: any
  }
}

interface Props {
  proteinText: string | null
  poseText: string | null
  pocketResidues: string[]
  interactions: {
    kind: string
    ligand_coord: number[]
    protein_coord: number[]
  }[]
  height?: number
}

/** Interactive WebGL molecular viewer (3Dmol.js): receptor + pocket + docked pose. */
export default function MoleculeViewer({
  proteinText,
  poseText,
  pocketResidues,
  interactions,
  height = 300,
}: Props) {
  const hostRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)
  const [showSurface, setShowSurface] = useState(true)
  const [spin, setSpin] = useState(false)
  const viewerRef = useRef<any>(null)
  const rebuildRef = useRef<() => void>(() => {})

  useEffect(() => {
    let cancelled = false
    const tryInit = (tries: number) => {
      if (cancelled) return
      if (!window.$3Dmol) {
        if (tries <= 0) {
          setError('3Dmol.js could not be loaded (offline?). The 3D view needs the CDN once.')
          return
        }
        setTimeout(() => tryInit(tries - 1), 400)
        return
      }
      if (!hostRef.current || viewerRef.current) return
      try {
        const viewer = window.$3Dmol.createViewer(hostRef.current, {
          backgroundColor: '#060A12',
          antialias: true,
        })
        viewerRef.current = viewer
        setReady(true)
      } catch (e) {
        setError('WebGL is unavailable in this browser — the 3D view cannot render.')
      }
    }
    tryInit(20)
    return () => {
      cancelled = true
      if (viewerRef.current) {
        viewerRef.current.clear()
        viewerRef.current = null
      }
    }
  }, [])

  // (re)build scene whenever data or toggles change
  useEffect(() => {
    rebuildRef.current = () => {
      const viewer = viewerRef.current
      if (!viewer || !proteinText) return
      try {
        viewer.clear()
        viewer.addModel(proteinText, 'pdb')
        viewer.setStyle({}, { cartoon: { color: '#3E5A76', opacity: 0.92 } })

        // group pocket residues by chain once
        const byChain: Record<string, number[]> = {}
        pocketResidues.forEach((label) => {
          const m = label.match(/^([A-Z0-9]+)(-?\d+)([A-Za-z]?)(?::(\w))?$/)
          if (!m) return
          const chain = m[4] || 'A'
          ;(byChain[chain] = byChain[chain] || []).push(parseInt(m[2], 10))
        })

        if (showSurface && pocketResidues.length) {
          Object.entries(byChain).forEach(([chain, resis]) => {
            try {
              viewer.addSurface(
                window.$3Dmol.SurfaceType.VDW,
                { color: '#14B8A6', opacity: 0.62 },
                { chain, resi: resis },
              )
            } catch {
              /* surface is a nice-to-have */
            }
          })
        }

        if (poseText) {
          viewer.addModel(poseText, 'sdf')
          viewer.setStyle({ model: 1 }, {
            stick: { radius: 0.16, colorscheme: 'greenCarbon' },
            sphere: { scale: 0.22, colorscheme: 'greenCarbon' },
          })
          // thin sticks for pocket residues, per chain (3Dmol `and` needs arrays)
          Object.entries(byChain).forEach(([chain, resis]) => {
            try {
              viewer.addStyle({ model: 0, chain, resi: resis }, {
                stick: { radius: 0.09, color: '#74809A', opacity: 0.9 },
              })
            } catch {
              /* cosmetic */
            }
          })
        }

        // hydrogen-bond / contact guides
        if (poseText) {
          interactions
            .filter((it) => it.kind === 'hbond' || it.kind === 'electrostatic')
            .slice(0, 10)
            .forEach((it) => {
              viewer.addLine({
                start: { x: it.ligand_coord[0], y: it.ligand_coord[1], z: it.ligand_coord[2] },
                end: { x: it.protein_coord[0], y: it.protein_coord[1], z: it.protein_coord[2] },
                dashed: true,
                dashLength: 0.08,
                gapLength: 0.06,
                color: '#FBBF24',
                linewidth: 2,
              })
            })
        }

        // frame on the pocket (falls back to ligand / whole protein)
        const primary = Object.entries(byChain)[0]
        const frameSel = primary
          ? { model: 0, chain: primary[0], resi: primary[1] }
          : poseText
            ? { model: 1 }
            : {}
        try {
          viewer.zoomTo(frameSel)
        } catch {
          viewer.zoomTo()
        }
        viewer.zoom(poseText ? 1.3 : 1.0)
        viewer.spin(spin ? 'y' : undefined)
        viewer.render()
      } catch (e) {
        setError('Could not render this structure.')
      }
    }
    if (ready) rebuildRef.current()
  }, [proteinText, poseText, pocketResidues, interactions, showSurface, spin, ready])

  if (error) {
    return (
      <div
        className="flex items-center justify-center rounded-xl border border-line bg-ink-900 px-6 text-center text-xs leading-relaxed text-fog-500"
        style={{ height }}
      >
        {error}
      </div>
    )
  }

  return (
    <div className="relative overflow-hidden rounded-xl border border-line bg-ink-900">
      <div ref={hostRef} style={{ height, width: '100%', position: 'relative' }} />
      <div className="absolute right-3 top-3 flex gap-1.5">
        <button
          onClick={() => setShowSurface((v) => !v)}
          className={`rounded-lg border px-2.5 py-1 text-[10.5px] font-medium backdrop-blur transition-colors ${
            showSurface
              ? 'border-accent/40 bg-accent/15 text-accent-bright'
              : 'border-line bg-ink-950/70 text-fog-400 hover:text-white'
          }`}
        >
          Pocket surface
        </button>
        <button
          onClick={() => setSpin((v) => !v)}
          className={`rounded-lg border px-2.5 py-1 text-[10.5px] font-medium backdrop-blur transition-colors ${
            spin
              ? 'border-quantum/40 bg-quantum/15 text-quantum-bright'
              : 'border-line bg-ink-950/70 text-fog-400 hover:text-white'
          }`}
        >
          Spin
        </button>
      </div>
      <div className="pointer-events-none absolute bottom-3 left-3 rounded-lg border border-line bg-ink-950/75 px-2.5 py-1 font-mono text-[10px] text-fog-500 backdrop-blur">
        receptor cartoon · <span className="text-accent">pocket surface</span> ·{' '}
        <span className="text-emerald-400">ligand</span> ·{' '}
        <span className="text-amber-soft">polar contacts</span>
      </div>
    </div>
  )
}

function pocketSelection(residues: string[]) {
  const byChain: Record<string, number[]> = {}
  residues.forEach((label) => {
    const m = label.match(/^([A-Z0-9]+)(-?\d+)([A-Za-z]?)(?::(\w))?$/)
    if (!m) return
    const chain = m[4] || 'A'
    ;(byChain[chain] = byChain[chain] || []).push(parseInt(m[2], 10))
  })
  const parts = Object.entries(byChain).map(([chain, resi]) => ({ chain, resi }))
  if (parts.length === 0) return { resi: [] }
  if (parts.length === 1) return parts[0]
  return { or: parts }
}
