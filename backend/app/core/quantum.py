"""Quantum refinement stage — VQE on an effective two-site Hamiltonian.

Classical docking treats electrons implicitly.  This stage adds an explicit
quantum-mechanical correction for the strongest non-covalent contact of each
docked pose:

  * the ligand donor/acceptor and the protein partner are modelled as two
    localized electronic sites (a two-site, two-orbital Hubbard dimer);
  * the site coupling ``t`` decays exponentially with the donor-acceptor
    distance, the on-site repulsion ``U`` is derived from chemical hardness and
    the level offset ``delta`` from the electronegativity difference;
  * the 4-mode second-quantized Hamiltonian is mapped to 4 qubits with
    Jordan-Wigner and its ground state is found with VQE (L-BFGS-B with parameter-shift gradients and a hardware
    efficient ansatz) on a statevector simulator;
  * the ground-state interaction energy  dE = E(coupled) - E(uncoupled)
    quantifies charge-transfer stabilization of the contact.

This is a proof-of-concept refinement — production systems would run VQE on
active-space ab initio Hamiltonians (PySCF/OpenFermion).  It is, however, a
real quantum algorithm running on a real qubit Hamiltonian, exactly the hybrid
quantum-classical pattern published for near-term drug discovery pipelines.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from qiskit import QuantumCircuit
from qiskit.quantum_info import SparsePauliOp, Statevector
from scipy.optimize import minimize

# ----------------------------------------------------------------------------- #
# Fermionic model
# ----------------------------------------------------------------------------- #

_I2 = np.eye(2, dtype=complex)
_Z = np.array([[1, 0], [0, -1]], dtype=complex)
_ANNIH = np.array([[0, 1], [0, 0]], dtype=complex)   # |0><1| : lowers occupation
_PAULIS = {"I": _I2, "X": np.array([[0, 1], [1, 0]], dtype=complex),
           "Y": np.array([[0, -1j], [1j, 0]], dtype=complex), "Z": _Z}


def _annihilate(mode: int, n_modes: int = 4) -> np.ndarray:
    """Jordan-Wigner annihilation operator on ``mode`` (16x16, little-endian)."""
    op = np.array([[1]], dtype=complex)
    for m in range(n_modes):
        factor = _ANNIH if m == mode else (_Z if m < mode else _I2)
        op = np.kron(op, factor)
    return op


def _number_operator(n_modes: int = 4) -> np.ndarray:
    c = [_annihilate(m, n_modes) for m in range(n_modes)]
    N = np.zeros((2 ** n_modes, 2 ** n_modes), dtype=complex)
    for m in range(n_modes):
        N += c[m].conj().T @ c[m]
    return N


def hubbard_dimer_matrix(t: float, U: float, delta: float) -> np.ndarray:
    """Two-site Hubbard Hamiltonian.

    Modes (little-endian bit order): 0 = site1 up, 1 = site2 up,
                                     2 = site1 down, 3 = site2 down

        H = -t sum_sigma (c1s' c2s + h.c.)        hopping
            + U sum_sigma n_1s n_1s'              on-site repulsion (site 1)
            + U sum_sigma n_2s n_2s'              on-site repulsion (site 2)
            + delta/2 sum_sigma (n_1s - n_2s)     site energy offset
    """
    n_modes = 4
    c = [_annihilate(m, n_modes) for m in range(n_modes)]
    cd = [op.conj().T for op in c]
    n = [cd[m] @ c[m] for m in range(n_modes)]

    site1 = [0, 2]
    site2 = [1, 3]
    H = np.zeros((2 ** n_modes, 2 ** n_modes), dtype=complex)
    for a, b in zip(site1, site2):
        H += -t * (cd[a] @ c[b] + cd[b] @ c[a])
        H += (delta / 2.0) * (n[a] - n[b])
    H += U * (n[site1[0]] @ n[site1[1]])
    H += U * (n[site2[0]] @ n[site2[1]])
    return H


def pauli_decompose(H: np.ndarray) -> list[tuple[str, float]]:
    """Exact expansion of a 4-qubit Hermitian matrix into the Pauli basis."""
    from itertools import product

    terms: list[tuple[str, float]] = []
    for label in ("".join(p) for p in product("IXYZ", repeat=4)):
        # Qiskit labels are big-endian strings over qubits q3..q0; the matrix
        # kron below follows the same convention.
        M = _PAULIS[label[0]]
        for ch in label[1:]:
            M = np.kron(M, _PAULIS[ch])
        coeff = np.trace(M.conj().T @ H) / 16.0
        if abs(coeff.real) > 1e-9:
            terms.append((label, float(coeff.real)))
    return terms


def hamiltonian_to_qubit(t: float, U: float, delta: float) -> SparsePauliOp:
    H = hubbard_dimer_matrix(t, U, delta)
    return SparsePauliOp.from_list(pauli_decompose(H))


# ----------------------------------------------------------------------------- #
# Variational quantum eigensolver
# ----------------------------------------------------------------------------- #

def _ansatz(n_qubits: int = 4, depth: int = 2) -> QuantumCircuit:
    """Hardware-efficient RY entangler ansatz."""
    qc = QuantumCircuit(n_qubits)
    n_params = (depth + 1) * n_qubits
    from qiskit.circuit import ParameterVector

    params = ParameterVector("theta", n_params)
    p = 0
    for _ in range(depth + 1):
        for q in range(n_qubits):
            qc.ry(params[p], q)
            p += 1
        for q in range(n_qubits):
            qc.cx(q, (q + 1) % n_qubits)
    qc.metadata = {"n_params": n_params}
    return qc


@dataclass
class VQEResult:
    energy: float
    exact_energy: float
    error: float
    iterations: int
    evaluations: int
    n_qubits: int = 4
    n_pauli_terms: int = 0
    ansatz_depth: int = 2

    def as_dict(self) -> dict:
        return {
            "energy_eh": round(self.energy, 6),
            "exact_energy_eh": round(self.exact_energy, 6),
            "error_eh": round(self.error, 8),
            "iterations": self.iterations,
            "evaluations": self.evaluations,
            "n_qubits": self.n_qubits,
            "n_pauli_terms": self.n_pauli_terms,
            "ansatz_depth": self.ansatz_depth,
        }


def run_vqe(t: float, U: float, delta: float, maxiter: int = 150, seed: int = 7,
            particle_penalty: float = 0.6) -> VQEResult:
    """VQE on the penalized Hamiltonian  H + λ(N-2)²  (half-filled dimer).

    The particle-number penalty pins the variational state to the physical
    two-electron sector — a standard technique when the ansatz does not
    conserve particle number.  The optimizer is L-BFGS-B driven by exact
    parameter-shift gradients (the RY ansatz satisfies the shift rule), with
    two random restarts.
    """
    Hmat = hubbard_dimer_matrix(t, U, delta)
    if particle_penalty > 0:
        N = _number_operator()
        dev = N - 2.0 * np.eye(16)
        Hmat = Hmat + particle_penalty * (dev @ dev)
    qop = SparsePauliOp.from_list(pauli_decompose(Hmat))
    Hq = qop.to_matrix()
    exact = float(np.linalg.eigvalsh(Hmat)[0].real)

    ansatz = _ansatz()
    n_params = ansatz.num_parameters
    rng = np.random.default_rng(seed)

    def energy_of(theta: np.ndarray) -> float:
        bound = ansatz.assign_parameters(theta)
        sv = Statevector(bound).data
        return float(np.real(sv.conj() @ (Hq @ sv)))

    def grad_of(theta: np.ndarray) -> np.ndarray:
        g = np.zeros(n_params)
        for i in range(n_params):
            tp = theta.copy(); tp[i] += np.pi / 2
            tm = theta.copy(); tm[i] -= np.pi / 2
            g[i] = 0.5 * (energy_of(tp) - energy_of(tm))
        return g

    best = None
    evals = 0
    iters = 0
    bounds = [(-np.pi, np.pi)] * n_params
    for start in rng.uniform(-0.8, 0.8, size=(2, n_params)):
        res = minimize(energy_of, start, jac=grad_of, method="L-BFGS-B",
                       bounds=bounds,
                       options={"maxiter": maxiter, "ftol": 1e-12, "gtol": 1e-9})
        evals += res.nfev + res.njev * 2 * n_params
        iters += int(getattr(res, "nit", 0) or 0)
        if best is None or res.fun < best:
            best = float(res.fun)

    return VQEResult(energy=best, exact_energy=exact, error=abs(best - exact),
                     iterations=int(iters), evaluations=int(evals),
                     n_pauli_terms=len(qop.to_list()))


# ----------------------------------------------------------------------------- #
# Contact -> Hamiltonian parameter mapping
# ----------------------------------------------------------------------------- #

# Distance in A between donor & acceptor heavy atoms at VdW contact
_REF_DIST = 2.9
_T0 = 0.045          # Ha, hopping at reference distance
_U0 = 0.28           # Ha, on-site repulsion scale

# Pauling electronegativities for level offsets
_CHI = {"H": 2.20, "C": 2.55, "N": 3.04, "O": 3.44, "F": 3.98, "S": 2.58, "P": 2.19}


def contact_parameters(distance: float, ligand_element: str, protein_element: str) -> dict:
    d = max(float(distance), 2.2)
    t = _T0 * math.exp(-(d - _REF_DIST) / 0.9)
    chi_l = _CHI.get(ligand_element, 2.55)
    chi_p = _CHI.get(protein_element, 2.55)
    delta = 1.4 * (chi_l - chi_p)          # Ha, level offset between the sites
    return {"t": round(t, 6), "U": _U0, "delta": round(delta, 6), "distance": round(d, 2)}


def interaction_energy(distance: float, ligand_element: str, protein_element: str,
                       maxiter: int = 150) -> dict:
    """VQE ground-state interaction energy of the contact, in hartree and eV."""
    params = contact_parameters(distance, ligand_element, protein_element)
    vqe_coupled = run_vqe(params["t"], params["U"], params["delta"], maxiter=maxiter)
    vqe_decoupled = run_vqe(0.0, params["U"], params["delta"], maxiter=maxiter)
    dE = vqe_coupled.energy - vqe_decoupled.energy
    dE_exact = vqe_coupled.exact_energy - vqe_decoupled.exact_energy
    return {
        "params": params,
        "delta_e_hartree": round(dE, 6),
        "delta_e_ev": round(dE * 27.2114, 4),
        "delta_e_exact_eh": round(dE_exact, 6),
        "vqe": vqe_coupled.as_dict(),
        "decoupled_energy_eh": round(vqe_decoupled.energy, 6),
    }
