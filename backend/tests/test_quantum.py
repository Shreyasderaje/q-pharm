"""Quantum module tests: Hubbard-dimer construction, Pauli mapping and VQE accuracy."""

import numpy as np
import pytest

from app.core.quantum import (
    hamiltonian_to_qubit,
    hubbard_dimer_matrix,
    pauli_decompose,
    run_vqe,
)


@pytest.mark.parametrize("t,U,delta", [(0.02, 0.28, 0.0), (0.05, 0.28, 0.1), (0.01, 0.28, -0.15)])
def test_pauli_decomposition_reproduces_matrix(t, U, delta):
    H = hubbard_dimer_matrix(t, U, delta)
    qop = hamiltonian_to_qubit(t, U, delta)
    Hq = qop.to_matrix()
    # Our kron convention (mode 0 = most significant factor) matches Qiskit's
    # label convention (leftmost label char = highest qubit = MSB), so the
    # qubit-operator matrix must equal the fermionic matrix exactly.
    assert np.allclose(H, Hq, atol=1e-8)


def test_hubbard_dimer_perturbation_limit():
    """At half filling (N=2 pinned by the penalty), E_gs = U/2 - sqrt((U/2)^2 + 4 t^2)."""
    from app.core.quantum import _number_operator

    t, U = 0.03, 0.30
    H = hubbard_dimer_matrix(t, U, 0.0)
    N = _number_operator()
    dev = N - 2.0 * np.eye(16)
    Hp = H + 0.6 * (dev @ dev)
    e_num = np.linalg.eigvalsh(Hp)[0].real
    e_ana = U / 2 - np.sqrt((U / 2) ** 2 + 4 * t ** 2)
    assert abs(e_num - e_ana) < 1e-9


@pytest.mark.parametrize("t,U,delta", [(0.04, 0.28, 0.05), (0.02, 0.28, -0.08)])
def test_vqe_finds_ground_state(t, U, delta):
    res = run_vqe(t, U, delta, maxiter=400)
    assert res.error < 5e-4, f"VQE error too large: {res.error}"
    assert res.n_qubits == 4
    assert res.n_pauli_terms > 0
    assert res.evaluations > 10


def test_interaction_energy_stabilises_contact():
    from app.core.quantum import interaction_energy

    out = interaction_energy(2.9, "N", "O", maxiter=250)
    # charge transfer should stabilise (negative) or be ~zero, never large positive
    assert out["delta_e_hartree"] < 1e-3
    assert "vqe" in out and out["vqe"]["n_qubits"] == 4
