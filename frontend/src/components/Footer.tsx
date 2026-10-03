import { Link } from 'react-router-dom'
import { Github } from 'lucide-react'
import Logo from './Logo'

export default function Footer() {
  return (
    <footer className="border-t border-line bg-ink-950">
      <div className="mx-auto max-w-7xl px-6 py-14">
        <div className="flex flex-col justify-between gap-10 md:flex-row">
          <div className="max-w-md">
            <Logo />
            <p className="mt-4 text-sm leading-relaxed text-fog-500">
              An open, quantum-accelerated drug repurposing engine. Built to give every
              researcher — anywhere — the screening tools that used to require a
              supercomputer budget.
            </p>
            <div className="mt-5 flex items-center gap-3">
              <span className="chip">
                <Github size={12} /> Open source · MIT
              </span>
              <span className="chip">v1.0.0</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-12 sm:grid-cols-3">
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-widest2 text-fog-500">Product</h4>
              <ul className="mt-4 space-y-2.5 text-sm text-fog-400">
                <li><Link to="/platform" className="hover:text-accent">Screening console</Link></li>
                <li><a href="/#pipeline" className="hover:text-accent">How it works</a></li>
                <li><a href="/#quantum" className="hover:text-accent">Quantum core</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-widest2 text-fog-500">Science</h4>
              <ul className="mt-4 space-y-2.5 text-sm text-fog-400">
                <li><a href="https://files.rcsb.org" target="_blank" rel="noreferrer" className="hover:text-accent">RCSB PDB</a></li>
                <li><a href="https://pubchem.ncbi.nlm.nih.gov" target="_blank" rel="noreferrer" className="hover:text-accent">PubChem</a></li>
                <li><a href="https://qiskit.org" target="_blank" rel="noreferrer" className="hover:text-accent">Qiskit</a></li>
                <li><a href="https://www.rdkit.org" target="_blank" rel="noreferrer" className="hover:text-accent">RDKit</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-widest2 text-fog-500">API</h4>
              <ul className="mt-4 space-y-2.5 text-sm text-fog-400">
                <li><a href="/api/health" className="hover:text-accent">Health check</a></li>
                <li><a href="/api/targets" className="hover:text-accent">Curated targets</a></li>
                <li><a href="/docs" className="hover:text-accent">OpenAPI docs</a></li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-12 border-t border-line pt-6">
          <p className="text-xs leading-relaxed text-fog-600">
            <span className="font-medium text-fog-400">Disclaimer.</span> Q-Pharm is a research
            and education project. Docking scores, quantum corrections and ADMET estimates are
            computational approximations produced by simplified models — they are hypothesis
            generators, not medical evidence. Nothing here is medical advice, and no output
            should be used for clinical decision-making. Always validate findings experimentally
            and consult qualified professionals.
          </p>
          <p className="mt-4 text-xs text-fog-600">
            © 2026 Q-Pharm Contributors · MIT License · Drug data via PubChem / DrugBank open
            resources · Structures via RCSB PDB
          </p>
        </div>
      </div>
    </footer>
  )
}
