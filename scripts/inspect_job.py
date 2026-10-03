import json, sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
r = d["result"]
print("=== SCREENING:", r["target"]["name"], "===")
print("screening:", r["screening"])
print("pocket:", r["pocket"]["n_residues"], "residues |", r["pocket"]["reference"])
print()
print(f"{'#':>3} {'drug':<20} {'dG':>7} {'comp':>6} {'q_dE_eV':>9} {'q_err':>9} {'ADMET':>5} {'ml':>5}")
for c in r["candidates"][:12]:
    q = c["quantum"]
    qe = f"{q['delta_e_ev']:.3f}" if q.get("used") else "-"
    qerr = f"{q['vqe']['error_eh']:.1e}" if q.get("used") else "-"
    a = c["admet"]
    print(f"{c['rank']:>3} {c['drug']['name']:<20} {c['docking']['score']:>7.1f} "
          f"{c['scores']['composite']:>6.3f} {qe:>9} {qerr:>9} {a['grade'] if a else '-':>5} "
          f"{c['ml']['p_druglike']:>5.2f}")
print()
top = r["candidates"][0]
print("TOP:", top["drug"]["name"], "| interactions:", len(top["docking"]["interactions"]))
for it in top["docking"]["interactions"][:6]:
    print("  ", it["kind"], it["ligand_atom"], "...", it["protein"], round(it["distance"], 2))
q = top["quantum"]
if q.get("used"):
    print("  VQE:", q["vqe"]["n_qubits"], "qubits,", q["vqe"]["n_pauli_terms"], "pauli terms, iters",
          q["vqe"]["iterations"], "err", q["vqe"]["error_eh"])
    print("  contact:", q["contact"], "params:", q["params"])
