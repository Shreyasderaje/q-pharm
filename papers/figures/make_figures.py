"""Generate publication figures for the Q-Pharm preprint.

Figure 1 — end-to-end Mpro screening results (real data from screening job
           6d671bd69fde: 60-drug library vs PDB 6LU7).
Figure 2 — Hubbard-dimer ground state: analytic formula vs exact
           diagonalization vs live VQE runs (computed here with
           app.core.quantum.run_vqe).

Output: vector PDFs, publication-styled.
"""

import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "backend"))

OUT = pathlib.Path(__file__).resolve().parent

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 8.5,
    "axes.titlesize": 9,
    "axes.labelsize": 8.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.6,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "legend.frameon": False,
    "pdf.fonttype": 42,
})

ACCENT = "#0F766E"
ACCENT_LIGHT = "#5EEAD4"
QUANTUM = "#6D5BD8"
INK = "#111827"

# ------------------------------------------------------------------ #
# Real screening data (PDB 6LU7, 60-drug run, 18,000 placements)
# ------------------------------------------------------------------ #

HITS = [  # (name, dG kcal/mol-like, composite, quantum dE eV or None)
    ("Amoxicillin",   -12.9, 0.700, -0.501),
    ("Mannitol",       -8.6, 0.670, -1.065),
    ("Zanamivir",      -8.6, 0.639, -1.566),
    ("Sulfasalazine", -14.6, 0.620, -0.513),
    ("Entecavir",      -7.6, 0.572, -0.441),
    ("Ceftriaxone",    -9.8, 0.558, -1.030),
    ("Sofosbuvir",     -8.2, 0.535, -0.610),
    ("Molnupiravir",   -7.5, 0.529, None),
    ("Ribavirin",      -5.5, 0.525, None),
    ("Dabigatran",     -8.6, 0.518, -0.437),
]

fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.6))

names = [h[0] for h in HITS][::-1]
dgs = [h[1] for h in HITS][::-1]
comps = [h[2] for h in HITS][::-1]
qes = [h[3] for h in HITS][::-1]

ax = axes[0]
bars = ax.barh(names, dgs, color=ACCENT, alpha=0.88, height=0.62)
ax.set_xlabel("Docking score $\\Delta G$ (kcal mol$^{-1}$, empirical)")
ax.set_title("(a) Docking scores", loc="left", fontweight="bold", fontsize=9)
ax.axvline(0, color="#9CA3AF", lw=0.6)
ax.set_xlim(-16.5, 1.5)
for b, v in zip(bars, dgs):
    ax.text(v - 0.25, b.get_y() + b.get_height() / 2, f"{v:.1f}",
            va="center", ha="right", fontsize=7, color=INK)
ax.tick_params(axis="y", length=0)

ax = axes[1]
cols = [QUANTUM if q is not None else "#B7C1D1" for q in qes]
bars = ax.barh(names, comps, color=cols, alpha=0.9, height=0.62)
ax.set_xlabel("Composite score $S$ (dimensionless)")
ax.set_title("(b) Composite ranking", loc="left", fontweight="bold", fontsize=9)
ax.set_xlim(0, 0.84)
for b, v, q in zip(bars, comps, qes):
    label = f"{v:.3f}" + (f"  ($\\Delta E$ = {q:+.2f} eV)" if q is not None else "")
    ax.text(v + 0.012, b.get_y() + b.get_height() / 2, label,
            va="center", ha="left", fontsize=7, color=INK)
ax.tick_params(axis="y", length=0)
ax.tick_params(labelleft=False)

fig.tight_layout(pad=0.6)
fig.savefig(OUT / "fig_screening.pdf", bbox_inches="tight")
plt.close(fig)
print("fig_screening.pdf written")

# ------------------------------------------------------------------ #
# Hubbard-dimer ground state: analytic vs exact vs VQE (live)
# ------------------------------------------------------------------ #

from app.core.quantum import hubbard_dimer_matrix, run_vqe  # noqa: E402

U = 0.28
t_vals = np.linspace(0.004, 0.08, 40)
e_analytic = U / 2 - np.sqrt((U / 2) ** 2 + 4 * t_vals ** 2)
e_exact = np.array([
    np.linalg.eigvalsh(hubbard_dimer_matrix(float(t), U, 0.0))[0].real
    for t in t_vals
])

vqe_t = np.array([0.01, 0.02, 0.03, 0.045, 0.06, 0.08])
vqe_e = np.array([run_vqe(float(t), U, 0.0, maxiter=150, seed=7).energy for t in vqe_t])
max_err = float(np.max(np.abs(vqe_e - (U / 2 - np.sqrt((U / 2) ** 2 + 4 * vqe_t ** 2)))))
print(f"max |VQE - analytic| = {max_err:.2e} Eh")

fig, ax = plt.subplots(figsize=(3.45, 2.5))
ax.plot(t_vals, e_analytic, color=ACCENT, lw=1.6, label="analytic  $\\frac{U}{2}-\\sqrt{(U/2)^2+4t^2}$")
ax.plot(t_vals, e_exact, color=QUANTUM, lw=1.0, ls=(0, (4, 2)), label="exact diagonalization")
ax.plot(vqe_t, vqe_e, "o", ms=4.5, mfc="white", mec=INK, mew=0.9, ls="none", label="VQE (12 params, L-BFGS-B)")
ax.set_xlabel("hopping amplitude $t$ (E$_h$)")
ax.set_ylabel("ground-state energy (E$_h$)")
ax.set_title("Hubbard-dimer ground state ($U$ = 0.28 E$_h$, $\\delta$ = 0)", loc="left", fontweight="bold")
ax.legend(fontsize=7, loc="lower left")
fig.tight_layout(pad=0.6)
fig.savefig(OUT / "fig_vqe.pdf", bbox_inches="tight")
plt.close(fig)
print(f"fig_vqe.pdf written (max VQE error {max_err:.1e} Eh)")
