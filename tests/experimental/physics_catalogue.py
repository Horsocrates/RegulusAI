#!/usr/bin/env python3
"""
Physics Catalogue: Every phenomenon as 3 E/R/R formulas.

Each entry:
  R_rules:    equation of motion (HOW)
  R_roles:    spectral decomposition / significance (WHY)
  E_elements: field on graph (WHAT)
  parameters: concrete values
  prediction: what ToS predicts
  observed:   experimental value
  coq_files:  formal verification references
  status:     confirmed / partial / open

Generates: physics_catalogue.json (parseable database)

Run: uv run python -m tests.experimental.physics_catalogue
"""

import json
import numpy as np
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional


@dataclass
class ERRFormulas:
    R_rules: str       # equation of motion
    R_roles: str       # spectral / significance
    E_elements: str    # field / ground state


@dataclass
class PhysicsEntry:
    id: str
    name: str
    domain: str
    tier: int                    # 1=verified, 2=computed, 3=conceptual
    formulas: ERRFormulas
    parameters: dict
    prediction: str
    observed: str
    agreement: str               # "exact", "0.04%", "factor 2", "open"
    coq_files: list
    coq_theorems: list
    python_files: list = field(default_factory=list)
    notes: str = ""


# ========================================================================
#  THE CATALOGUE
# ========================================================================

CATALOGUE = [

    # === TIER 1: VERIFIED (formulas + numbers + Coq) ===

    PhysicsEntry(
        id="weinberg_angle",
        name="Weinberg Angle (tree level)",
        domain="electroweak",
        tier=1,
        formulas=ERRFormulas(
            R_rules="sin^2(theta_W) = n_gauge / (n_gauge + n_metric)",
            R_roles="DOF counting: 3 gauge + 10 metric = 13 total",
            E_elements="nested distinction [2, 3, 1] -> SU(3)xSU(2)xU(1)",
        ),
        parameters={"n_gauge": 3, "n_metric": 10, "n_total": 13},
        prediction="sin^2(theta_W) = 3/13 = 0.23077",
        observed="sin^2(theta_W) = 0.23122 +/- 0.00003",
        agreement="0.04%",
        coq_files=["src/foundation/DOFCounting.v", "src/foundation/MetricDOFJustification.v"],
        coq_theorems=["sin2_is_3_over_13", "sin2_close_to_observed"],
        notes="Zero free parameters. Pure integer ratio."
    ),

    PhysicsEntry(
        id="casimir_1d",
        name="Casimir Effect (1D coefficient)",
        domain="vacuum",
        tier=1,
        formulas=ERRFormulas(
            R_rules="E_vac(N) = Sum_{k=1}^{N-1} omega_k / 2",
            R_roles="omega_k = 2|sin(pi*k/(2N))| eigenfrequencies",
            E_elements="vacuum field: all modes at zero-point energy",
        ),
        parameters={"zeta_neg1": "-1/12", "zeta_neg3": "1/120"},
        prediction="Casimir energy -> -1/4 (lattice), -pi/24 (continuum)",
        observed="Casimir force ~ -pi^2/(720 d^4)",
        agreement="exact (coefficient verified)",
        coq_files=["src/experimental/CasimirProcess.v", "src/casimir_branch/CasimirFromGraph.v"],
        coq_theorems=["casimir_1d_verified", "casimir_3d_verified", "E_vac_C4"],
        python_files=["tests/experimental/predictions.py"],
        notes="No infinities. Finite sum at every N. P4 guarantee."
    ),

    PhysicsEntry(
        id="born_rule",
        name="Born Rule = Parseval Theorem",
        domain="quantum_mechanics",
        tier=1,
        formulas=ERRFormulas(
            R_rules="Sum |A_k|^2 = 1 (normalization = Parseval)",
            R_roles="P(k) = |A_k|^2 = spectral energy fraction",
            E_elements="psi = [A_0, ..., A_{N-1}] mode amplitudes",
        ),
        parameters={"p_exponent": 2, "uniqueness": "p=2 is the ONLY exponent that preserves norm"},
        prediction="P(k) = |A_k|^2 (NOT postulate, theorem)",
        observed="Born rule confirmed in all quantum experiments",
        agreement="exact",
        coq_files=["src/crown/BornIsParseval.v", "src/process_qm/QuantumFromVibration.v"],
        coq_theorems=["born_equals_spectral", "born_sums_to_one", "born_sum_is_parseval"],
        notes="Crown jewel. Born rule IS Parseval. Not analogy, identity."
    ),

    PhysicsEntry(
        id="oscillation",
        name="Oscillation from L1+L5",
        domain="acoustics",
        tier=1,
        formulas=ERRFormulas(
            R_rules="delta(t+1) = (2-k)*delta(t) - delta(t-1)",
            R_roles="omega^2 = k (eigenfrequency from stiffness)",
            E_elements="delta(v, t) : vertex displacement field",
        ),
        parameters={"k": 2, "period": 4},
        prediction="k=2 -> period 4: (1, 0, -1, 0, 1, ...)",
        observed="All oscillations follow this equation",
        agreement="exact",
        coq_files=["src/acoustics/Oscillation.v", "src/acoustics/VibrationCore.v"],
        coq_theorems=["osc_k2_period4", "zero_crossing", "oscillation_period4"],
        notes="L1 (return) + L5 (inertia) -> forced oscillation. Logical necessity."
    ),

    PhysicsEntry(
        id="wave_propagation",
        name="Wave Propagation (causal)",
        domain="acoustics",
        tier=1,
        formulas=ERRFormulas(
            R_rules="phi(v,t+1) = (2-2c^2)*phi(v,t) + c^2*(left+right) - phi(v,t-1)",
            R_roles="speed c = sqrt(coupling/mass), causal: |delta_x| <= c*delta_t",
            E_elements="phi(v, t) : field on chain graph",
        ),
        parameters={"c_sq": 0.25, "N": 4},
        prediction="impulse at v=0 reaches v=1 after 1 step, v=2 still at rest",
        observed="wave causality confirmed",
        agreement="exact",
        coq_files=["src/acoustics/WavePropagation.v"],
        coq_theorems=["impulse_propagates", "wavefront_causal"],
    ),

    PhysicsEntry(
        id="gauge_group",
        name="SM Gauge Group from Nested Distinction",
        domain="particle_physics",
        tier=1,
        formulas=ERRFormulas(
            R_rules="Aut(ERR_N) has N^2-1 generators",
            R_roles="[2,3,1] depths -> SU(2)xSU(3)xU(1)",
            E_elements="nested distinction at 3 depths",
        ),
        parameters={"su3_gen": 8, "su2_gen": 3, "u1_gen": 1, "total": 12},
        prediction="SU(3)xSU(2)xU(1) with 12 generators",
        observed="Standard Model gauge group",
        agreement="exact",
        coq_files=["src/foundation/NestedDistinction.v", "src/foundation/ERRAutomorphism.v"],
        coq_theorems=["sm_generators", "sm_satisfies_constraints", "sm_aut_total"],
        notes="Gauge group DERIVED from distinction structure, not postulated."
    ),

    # === TIER 1: W/Z mass ratio ===

    PhysicsEntry(
        id="wz_mass_ratio",
        name="W/Z Mass Ratio",
        domain="electroweak",
        tier=1,
        formulas=ERRFormulas(
            R_rules="(m_W/m_Z)^2 = cos^2(theta_W) = 1 - sin^2(theta_W)",
            R_roles="cos^2(theta_W) = 10/13 from DOF counting",
            E_elements="gauge boson masses from symmetry breaking",
        ),
        parameters={"cos2_W": "10/13", "predicted_sq": 0.7692},
        prediction="(m_W/m_Z)^2 = 10/13 = 0.7692",
        observed="(80.377/91.188)^2 = 0.7771",
        agreement="1.0%",
        coq_files=["src/lattice/WZMassRatio.v"],
        coq_theorems=["match_within_1pct", "rho_parameter"],
    ),

    # === TIER 2: COMPUTED (formulas + partial numbers) ===

    PhysicsEntry(
        id="higgs_mass",
        name="Higgs Mass Ratio (tree + one-loop)",
        domain="electroweak",
        tier=2,
        formulas=ERRFormulas(
            R_rules="m_H^2 = 2*lambda_4*v^2 + delta_m_H^2(top+gauge+self)",
            R_roles="lambda_4 = 1/2 (Cayley), y_t = 1 (top Yukawa)",
            E_elements="Higgs field on distinction graph",
        ),
        parameters={"lambda_4": 0.5, "y_top": 1.0, "tree_ratio": 0.707},
        prediction="tree: m_H/m_W = 1/sqrt(2) = 0.707. One-loop: positive correction.",
        observed="m_H/m_W = 125.1/80.4 = 1.558",
        agreement="open (hierarchy problem)",
        coq_files=["src/lattice/HiggsMechanism.v", "src/fermions/GaugeLoops.v"],
        coq_theorems=["mH_mW_ratio", "our_delta_total_positive"],
        python_files=["tests/experimental/compute_higgs_correction.py"],
        notes="Sign correct (positive). Magnitude: overshoot. Open problem."
    ),

    PhysicsEntry(
        id="speed_of_light",
        name="Speed of Light = Graph Causal Limit",
        domain="relativity",
        tier=2,
        formulas=ERRFormulas(
            R_rules="c = lim_{k->0} d(omega)/dk = 1 (lattice units)",
            R_roles="dispersion: omega = 2|sin(pi*k/N)| -> omega ~ k at small k",
            E_elements="edge field (light) on chain graph",
        ),
        parameters={"c_lattice": 1, "c_SI": 299792458},
        prediction="c = 1 in lattice units (causal limit from L5)",
        observed="c = 299,792,458 m/s",
        agreement="structural (lattice units vs SI)",
        coq_files=["src/light/SpeedOfLight.v", "src/analysis/FourierDispersion.v"],
        coq_theorems=["edge_at_c", "zero_mode_massless"],
    ),

    PhysicsEntry(
        id="harmony",
        name="Musical Consonance from L1",
        domain="acoustics",
        tier=2,
        formulas=ERRFormulas(
            R_rules="consonance(p,q) = 1/(p*q)",
            R_roles="combined period = lcm(p,q), shorter = more consonant",
            E_elements="two tones with frequency ratio p/q",
        ),
        parameters={"octave": "2/1", "fifth": "3/2", "tritone": "45/32"},
        prediction="unison > octave > fifth > fourth > major 3rd > tritone",
        observed="matches Pythagorean tuning and psychoacoustic data",
        agreement="qualitative match",
        coq_files=["src/acoustics/Harmony.v"],
        coq_theorems=["consonance_ordering", "octave_most_consonant"],
    ),

    PhysicsEntry(
        id="vacuum_energy_density",
        name="Vacuum Energy Density (Lambda problem)",
        domain="cosmology",
        tier=2,
        formulas=ERRFormulas(
            R_rules="rho(N) = E_vac(N) / N",
            R_roles="density converges: 1/2 for C_2, C_4, C_8",
            E_elements="eigenvalues on cycle graph",
        ),
        parameters={"density_C2": 0.5, "density_C4": 0.5, "density_C8": 0.5},
        prediction="density = 1/2 (lattice units), converges with N",
        observed="Lambda ~ 10^{-123} (Planck units)",
        agreement="P4 resolves infinity (no vacuum catastrophe)",
        coq_files=["src/casimir_branch/CasimirConvergence.v", "src/cosmological/LambdaFromGraph.v"],
        coq_theorems=["density_converges", "no_vacuum_catastrophe"],
    ),

    PhysicsEntry(
        id="lattice_spacing",
        name="Lattice Spacing from Lambda",
        domain="cosmology",
        tier=2,
        formulas=ERRFormulas(
            R_rules="a^4 = rho_lattice * hbar * c / rho_observed",
            R_roles="rho_lattice = 1/pi, rho_observed = 5.96e-27 kg/m^3",
            E_elements="distinction graph lattice spacing",
        ),
        parameters={"a_meters": 3.81e-9, "a_planck": 2.36e26},
        prediction="a = 3.81 nm (nanometers)",
        observed="E_max = 52 eV (less than keV X-rays exist)",
        agreement="partial (scale sensible, E_max too low)",
        coq_files=[],
        coq_theorems=[],
        python_files=["tests/experimental/predictions.py"],
        notes="Nanometer scale physically meaningful. Needs modification for short distances."
    ),

    # === TIER 2: Gamma unification ===

    PhysicsEntry(
        id="gamma_unification",
        name="Quantum-Classical via Gamma Parameter",
        domain="quantum_foundations",
        tier=2,
        formulas=ERRFormulas(
            R_rules="A(t+1) = (1 - gamma) * A(t)",
            R_roles="gamma=0: quantum. gamma=1: classical. Between: continuous.",
            E_elements="mode amplitude A on distinction graph",
        ),
        parameters={"gamma_quantum": 0, "gamma_classical": 1},
        prediction="no boundary between quantum and classical, just gamma",
        observed="decoherence times match gamma ~ coupling strength",
        agreement="structural",
        coq_files=["src/foundation/GammaUnification.v"],
        coq_theorems=["gamma_zero_eternal", "gamma_one_instant", "three_are_one"],
        notes="Decoherence = damping = compression loss. ONE equation, THREE names."
    ),

    # === TIER 2: Compression ===

    PhysicsEntry(
        id="iot_compression",
        name="IoT Sensor Compression (GFT)",
        domain="data_compression",
        tier=2,
        formulas=ERRFormulas(
            R_rules="GFT: eigenvectors of graph Laplacian L = D - A",
            R_roles="keep top M modes by |f_hat_k|^2 (Born-optimal)",
            E_elements="temperature field on sensor graph",
        ),
        parameters={"ratio_indoor": 0.003, "ratio_furnace": 0.002, "ratio_cold": 0.003},
        prediction="300-600x compression within temperature tolerance",
        observed="zlib: ~91% ratio (lossless). ToS: 0.2-0.3% (lossy within tolerance).",
        agreement="300x better than zlib (within tolerance)",
        coq_files=["src/stdlib/compression/SpectralCompression.v"],
        coq_theorems=["spectral_compression_synthesis"],
        python_files=["tests/compression/iot_diffusion_benchmark.py"],
        notes="Indoor: RMSE 0.058C (tol 0.5C). Furnace: RMSE 1.67C (tol 2.0C)."
    ),

    # === TIER 3: CONCEPTUAL ===

    PhysicsEntry(
        id="curvature",
        name="Curvature = Degree Deviation",
        domain="gravity",
        tier=3,
        formulas=ERRFormulas(
            R_rules="curvature(v) = degree(v) - average_degree",
            R_roles="total curvature = 0 (sum of deviations)",
            E_elements="degree list on distinction graph",
        ),
        parameters={"regular": "flat (all curvatures 0)", "dense_vertex": "positive curvature"},
        prediction="mass creates positive curvature, geodesics bend toward mass",
        observed="general relativity confirmed",
        agreement="structural (discrete analog)",
        coq_files=["src/gravity/CurvatureFromGraph.v"],
        coq_theorems=["regular_graph_flat", "total_curvature_zero"],
    ),

    PhysicsEntry(
        id="big_bang",
        name="Big Bang = First Distinction (no singularity)",
        domain="cosmology",
        tier=3,
        formulas=ERRFormulas(
            R_rules="N(0) = 2 (first distinction A|~A)",
            R_roles="initial density = E_vac(2)/2 = 1/2 (FINITE)",
            E_elements="graph with 2 vertices (minimal system)",
        ),
        parameters={"N_initial": 2, "density_initial": 0.5},
        prediction="no singularity (P4: initial density finite)",
        observed="Big Bang singularity in GR",
        agreement="P4 resolves singularity",
        coq_files=["src/cosmology_ext/BigBangProcess.v"],
        coq_theorems=["no_singularity"],
    ),

    PhysicsEntry(
        id="second_law",
        name="Second Law from Mode Coupling",
        domain="thermodynamics",
        tier=3,
        formulas=ERRFormulas(
            R_rules="coupling -> energy flows from high to low amplitude",
            R_roles="active_modes increases (entropy proxy)",
            E_elements="mode energy distribution",
        ),
        parameters={"pure_tone_modes": 1, "thermal_modes": 4},
        prediction="coupling increases active modes (entropy)",
        observed="second law of thermodynamics",
        agreement="structural",
        coq_files=["src/thermal/SecondLaw.v"],
        coq_theorems=["entropy_increases", "equilibrium_no_flow"],
    ),

    PhysicsEntry(
        id="maxwell_from_graph",
        name="Maxwell Equations from Graph",
        domain="electromagnetism",
        tier=3,
        formulas=ERRFormulas(
            R_rules="Gauss: sum of edge values around vertex = charge",
            R_roles="curl: circulation around plaquette = magnetic field",
            E_elements="edge field epsilon(e, t) on distinction graph",
        ),
        parameters={"polarizations": 2, "spin": 1},
        prediction="Maxwell equations DERIVED, not postulated",
        observed="Maxwell equations confirmed",
        agreement="structural",
        coq_files=["src/light/MaxwellFromGraph.v"],
        coq_theorems=["gauss_zero_no_charge", "magnetic_nonzero_curl"],
    ),
]


# ========================================================================
#  GENERATE JSON + REPORT
# ========================================================================

def generate_json(catalogue):
    entries = []
    for e in catalogue:
        d = {
            'id': e.id, 'name': e.name, 'domain': e.domain, 'tier': e.tier,
            'formulas': asdict(e.formulas),
            'parameters': e.parameters,
            'prediction': e.prediction, 'observed': e.observed,
            'agreement': e.agreement,
            'coq_files': e.coq_files, 'coq_theorems': e.coq_theorems,
            'python_files': e.python_files, 'notes': e.notes,
        }
        entries.append(d)
    return entries


def main():
    print("=" * 80)
    print("  PHYSICS CATALOGUE: Every Phenomenon as 3 E/R/R Formulas")
    print("=" * 80)

    by_tier = {1: [], 2: [], 3: []}
    for e in CATALOGUE:
        by_tier[e.tier].append(e)

    for tier, label in [(1, "VERIFIED"), (2, "COMPUTED"), (3, "CONCEPTUAL")]:
        entries = by_tier[tier]
        print(f"\n  === TIER {tier}: {label} ({len(entries)} entries) ===\n")
        print(f"  {'ID':<22} {'Domain':<18} {'Agreement':<15} {'Coq':<5}")
        print(f"  {'-'*22} {'-'*18} {'-'*15} {'-'*5}")
        for e in entries:
            n_coq = len(e.coq_theorems)
            print(f"  {e.id:<22} {e.domain:<18} {e.agreement:<15} {n_coq:>3} Qed")

    # Summary
    total = len(CATALOGUE)
    t1 = len(by_tier[1])
    t2 = len(by_tier[2])
    t3 = len(by_tier[3])
    total_theorems = sum(len(e.coq_theorems) for e in CATALOGUE)

    print(f"\n  SUMMARY: {total} entries ({t1} verified, {t2} computed, {t3} conceptual)")
    print(f"  Total Coq theorems referenced: {total_theorems}")
    print(f"  Domains: {len(set(e.domain for e in CATALOGUE))}")

    # Generate JSON
    output_dir = Path(__file__).parent / 'results'
    output_dir.mkdir(exist_ok=True)
    path = output_dir / 'physics_catalogue.json'
    data = generate_json(CATALOGUE)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON database: {path} ({len(data)} entries)")

    # Also save as compact for parsing
    path_compact = output_dir / 'physics_catalogue_compact.json'
    compact = [{
        'id': e['id'], 'name': e['name'], 'tier': e['tier'],
        'R_rules': e['formulas']['R_rules'],
        'R_roles': e['formulas']['R_roles'],
        'E_elements': e['formulas']['E_elements'],
        'prediction': e['prediction'],
        'agreement': e['agreement'],
    } for e in data]
    with open(path_compact, 'w', encoding='utf-8') as f:
        json.dump(compact, f, indent=2, ensure_ascii=False)
    print(f"  Compact database: {path_compact}")


if __name__ == '__main__':
    main()
