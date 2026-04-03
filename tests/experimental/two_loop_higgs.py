#!/usr/bin/env python3
"""
Two-Loop Higgs Mass Refinement on ToS Lattice

One-loop: δm_H² = top(neg) + gauge(pos) + self(pos) = POSITIVE but OVERSHOOT.
Two-loop: add O(coupling²) corrections that REDUCE the overshoot.

Key two-loop effects:
1. Top-gauge mixing: top loop with gauge propagator insertion → reduces gauge
2. Gauge self-energy: gauge boson propagator gets corrected → effective g² runs
3. Higgs self-energy: λ runs down at two-loop → self-loop reduced
4. Fermion mass renormalization: m_t gets corrected → top loop changes

Run: uv run python -m tests.experimental.two_loop_higgs
"""

import numpy as np
import json
from pathlib import Path


def loop_sum(N, m_sq):
    """One-loop sum: (1/N) * Σ_{k=1}^{N-1} 1/(sin²(πk/N) + m²)."""
    return sum(1.0 / (np.sin(np.pi * k / N)**2 + m_sq) for k in range(1, N)) / N


def loop_sum_sq(N, m_sq):
    """Two-loop bubble: (1/N) * Σ 1/(sin²+m²)²."""
    return sum(1.0 / (np.sin(np.pi * k / N)**2 + m_sq)**2 for k in range(1, N)) / N


def sunset_sum(N, m1_sq, m2_sq):
    """Two-loop sunset: (1/N²) * Σ_{k,q} 1/((sin²k+m1²)(sin²q+m2²))."""
    s = 0
    for k in range(1, N):
        for q in range(1, N):
            sk = np.sin(np.pi * k / N)**2 + m1_sq
            sq = np.sin(np.pi * q / N)**2 + m2_sq
            s += 1.0 / (sk * sq)
    return s / (N * N)


def one_loop(N, y_t=1.0, N_c=3, g_sq=0.42, lam=0.5,
             m_t_sq=1.0, m_W_sq=0.105, m_H_sq=1.0):
    """One-loop correction (from compute_higgs_correction.py)."""
    top = -N_c * y_t**2 * loop_sum(N, m_t_sq)
    gauge = 3 * g_sq * loop_sum(N, m_W_sq)
    self_ = 3 * lam**2 * loop_sum(N, m_H_sq)
    return top, gauge, self_


def two_loop_corrections(N, y_t=1.0, N_c=3, g_sq=0.42, lam=0.5,
                          m_t_sq=1.0, m_W_sq=0.105, m_H_sq=1.0):
    """Two-loop corrections (leading order)."""

    # 1. Running of g² at one-loop: g²_eff = g² * (1 - b₀*g²*L)
    #    b₀ for SU(2): b₀ = 19/6 (with fermions)
    #    L = loop_sum ≈ ln(N) proxy
    L_gauge = loop_sum(N, m_W_sq)
    b0_su2 = 19.0 / 6
    g_sq_running = g_sq * (1 - b0_su2 * g_sq * L_gauge / (16 * np.pi**2))
    g_sq_running = max(g_sq_running, 0.01)  # don't go negative

    # 2. Running of λ: λ_eff = λ + (12λ² + ... - 12y_t⁴)/(16π²) * L
    L_higgs = loop_sum(N, m_H_sq)
    beta_lam = (12 * lam**2 - 12 * y_t**4 + 6 * g_sq**2) / (16 * np.pi**2)
    lam_running = lam + beta_lam * L_higgs
    lam_running = max(lam_running, 0.01)

    # 3. Running of y_t: y_t² decreases (asymptotically free in QCD)
    L_top = loop_sum(N, m_t_sq)
    # β_yt ≈ y_t(9y_t²/2 - 8g_s²)/(16π²), g_s²≈1.2
    g_s_sq = 1.2  # strong coupling
    beta_yt_sq = y_t**2 * (9 * y_t**2 / 2 - 8 * g_s_sq) / (16 * np.pi**2)
    y_t_running_sq = y_t**2 + beta_yt_sq * L_top
    y_t_running_sq = max(y_t_running_sq, 0.01)

    # 4. Two-loop top: -N_c * y_t⁴ * sunset (top × Higgs)
    two_loop_top = -N_c * y_t**4 * sunset_sum(N, m_t_sq, m_H_sq)

    # 5. Two-loop gauge: g⁴ * bubble²
    two_loop_gauge = 3 * g_sq**2 * loop_sum_sq(N, m_W_sq)

    # 6. Two-loop self: λ³ * bubble²
    two_loop_self = 3 * lam**3 * loop_sum_sq(N, m_H_sq)

    return {
        'g_sq_running': g_sq_running,
        'lam_running': lam_running,
        'y_t_sq_running': y_t_running_sq,
        'two_loop_top': two_loop_top,
        'two_loop_gauge': two_loop_gauge,
        'two_loop_self': two_loop_self,
    }


def full_correction(N, **kwargs):
    """One-loop + two-loop combined."""
    top1, gauge1, self1 = one_loop(N, **kwargs)
    one_loop_total = top1 + gauge1 + self1

    tl = two_loop_corrections(N, **kwargs)

    # Use running couplings for one-loop
    top1r, gauge1r, self1r = one_loop(
        N,
        y_t=np.sqrt(tl['y_t_sq_running']),
        g_sq=tl['g_sq_running'],
        lam=tl['lam_running'],
        **{k: v for k, v in kwargs.items() if k not in ['y_t', 'g_sq', 'lam']}
    )
    one_loop_running = top1r + gauge1r + self1r

    # Two-loop explicit
    two_loop_explicit = tl['two_loop_top'] + tl['two_loop_gauge'] + tl['two_loop_self']

    return {
        'one_loop_fixed': one_loop_total,
        'one_loop_running': one_loop_running,
        'two_loop_explicit': two_loop_explicit,
        'total_running': one_loop_running + two_loop_explicit,
        'total_fixed_plus_2L': one_loop_total + two_loop_explicit,
        'running_couplings': tl,
        'components_1L': {'top': top1, 'gauge': gauge1, 'self': self1},
        'components_1L_running': {'top': top1r, 'gauge': gauge1r, 'self': self1r},
        'components_2L': {
            'top': tl['two_loop_top'],
            'gauge': tl['two_loop_gauge'],
            'self': tl['two_loop_self'],
        },
    }


def main():
    print("=" * 80)
    print("  TWO-LOOP HIGGS MASS REFINEMENT ON ToS LATTICE")
    print("=" * 80)

    m_W_sq = 0.105

    print(f"\n  {'N':>5} {'1L-fixed':>9} {'1L-run':>9} {'2L-expl':>9} "
          f"{'TOTAL':>9} {'m_H^2':>8} {'m_H/m_W':>8}")
    print(f"  {'-'*5} {'-'*9} {'-'*9} {'-'*9} {'-'*9} {'-'*8} {'-'*8}")

    results = []
    for N in [4, 8, 16, 32, 64, 128, 256]:
        r = full_correction(N)
        total = r['total_running']
        mH_sq = 1.0 + total
        ratio = np.sqrt(max(mH_sq, 0) / m_W_sq) if mH_sq > 0 else 0

        results.append({'N': N, **r, 'mH_sq': mH_sq, 'ratio': ratio})

        print(f"  {N:>5} {r['one_loop_fixed']:>9.4f} {r['one_loop_running']:>9.4f} "
              f"{r['two_loop_explicit']:>9.4f} {total:>9.4f} "
              f"{mH_sq:>8.4f} {ratio:>8.4f}")

    print(f"\n  Tree:     m_H/m_W = {1/np.sqrt(2):.4f}")
    print(f"  Observed: m_H/m_W = 1.558")

    # Running couplings
    print(f"\n  {'='*60}")
    print(f"  RUNNING COUPLINGS")
    print(f"  {'='*60}")
    print(f"  {'N':>5} {'g^2':>8} {'lambda':>8} {'y_t^2':>8}")
    print(f"  {'-'*5} {'-'*8} {'-'*8} {'-'*8}")
    for r in results:
        rc = r['running_couplings']
        print(f"  {r['N']:>5} {rc['g_sq_running']:>8.4f} {rc['lam_running']:>8.4f} "
              f"{rc['y_t_sq_running']:>8.4f}")

    # Components at N=64
    print(f"\n  {'='*60}")
    print(f"  COMPONENT ANALYSIS (N=64)")
    print(f"  {'='*60}")
    r64 = next(r for r in results if r['N'] == 64)

    print(f"\n  ONE-LOOP (fixed couplings):")
    for k, v in r64['components_1L'].items():
        print(f"    {k:<8} {v:>+9.4f}")

    print(f"\n  ONE-LOOP (running couplings):")
    for k, v in r64['components_1L_running'].items():
        print(f"    {k:<8} {v:>+9.4f}")

    print(f"\n  TWO-LOOP (explicit):")
    for k, v in r64['components_2L'].items():
        print(f"    {k:<8} {v:>+9.4f}")

    print(f"\n  TOTALS:")
    print(f"    1L fixed:           {r64['one_loop_fixed']:>+9.4f}")
    print(f"    1L running:         {r64['one_loop_running']:>+9.4f}")
    print(f"    2L explicit:        {r64['two_loop_explicit']:>+9.4f}")
    print(f"    1L_running + 2L:    {r64['total_running']:>+9.4f}")

    # VERDICT
    print(f"\n  {'='*60}")
    print(f"  VERDICT")
    print(f"  {'='*60}")

    r_final = results[-1]
    total = r_final['total_running']
    mH_sq = r_final['mH_sq']
    ratio = r_final['ratio']

    print(f"\n  At N={r_final['N']}:")
    print(f"    One-loop (fixed):  {r_final['one_loop_fixed']:>+.4f} -> m_H/m_W = "
          f"{np.sqrt(max(1+r_final['one_loop_fixed'],0)/m_W_sq):.4f}")
    print(f"    Two-loop total:    {total:>+.4f} -> m_H/m_W = {ratio:.4f}")
    print(f"    Observed:                          m_H/m_W = 1.558")

    if ratio < np.sqrt(max(1 + r_final['one_loop_fixed'], 0) / m_W_sq):
        print(f"\n    Two-loop REDUCES overshoot (running couplings tame gauge loop)")
    else:
        print(f"\n    Two-loop doesn't help with overshoot")

    if 1.0 < ratio < 3.0:
        print(f"    IN RANGE: two-loop brings ratio toward observed!")
    elif ratio > 3.0:
        print(f"    STILL OVERSHOOTING: need proper SM normalization of gauge loop")
    else:
        print(f"    UNDERSHOOTING: need more positive contributions")

    # Save
    output_dir = Path(__file__).parent / 'results'
    output_dir.mkdir(exist_ok=True)
    path = output_dir / 'two_loop_results.json'
    save_results = []
    for r in results:
        save_results.append({
            'N': r['N'], 'mH_sq': r['mH_sq'], 'ratio': r['ratio'],
            'one_loop_fixed': r['one_loop_fixed'],
            'one_loop_running': r['one_loop_running'],
            'two_loop_explicit': r['two_loop_explicit'],
            'total': r['total_running'],
        })
    with open(path, 'w') as f:
        json.dump(save_results, f, indent=2)
    print(f"\n  Results saved to {path}")


if __name__ == '__main__':
    main()
