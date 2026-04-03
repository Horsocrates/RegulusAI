#!/usr/bin/env python3
"""
Compute one-loop Higgs mass correction on ToS lattice.
Top quark (negative) + gauge bosons (positive) + Higgs self (positive).
Compare with observed m_H/m_W = 1.558.

Run: uv run python -m tests.experimental.compute_higgs_correction
"""

import numpy as np


def loop_sum(N, m_sq):
    """One-loop sum: (1/N) * sum_{k=1}^{N-1} 1/(sin^2(pi*k/N) + m^2)."""
    return sum(1.0 / (np.sin(np.pi * k / N)**2 + m_sq) for k in range(1, N)) / N


def total_correction(N, y_t=1.0, N_c=3, g_sq=0.42, lam=0.5,
                     m_t_sq=1.0, m_W_sq=0.105, m_H_sq=1.0):
    """Total one-loop correction to m_H^2."""
    top = -N_c * y_t**2 * loop_sum(N, m_t_sq)
    gauge = 3 * g_sq * loop_sum(N, m_W_sq)
    higgs_self = 3 * lam**2 * loop_sum(N, m_H_sq)
    return top, gauge, higgs_self, top + gauge + higgs_self


def main():
    print("=" * 80)
    print("  ONE-LOOP HIGGS MASS CORRECTION ON ToS LATTICE")
    print("=" * 80)

    print(f"\n  Couplings: y_t=1, N_c=3, g^2=0.42, lambda=1/2")
    print(f"  Masses (lattice): m_t^2=1, m_W^2=0.105, m_H^2=1 (tree)")

    print(f"\n  {'N':>5} {'top':>9} {'gauge':>9} {'self':>9} {'TOTAL':>9} "
          f"{'m_H^2':>8} {'m_H/m_W':>8} {'Status':>12}")
    print(f"  {'-'*5} {'-'*9} {'-'*9} {'-'*9} {'-'*9} {'-'*8} {'-'*8} {'-'*12}")

    for N in [4, 8, 16, 32, 64, 128, 256, 512, 1024]:
        top, gauge, self_, total = total_correction(N)
        mH_sq = 1.0 + total
        mW_sq = 0.105

        if mH_sq > 0:
            ratio = np.sqrt(mH_sq / mW_sq)
            status = "OK" if ratio > 0.707 else "decreased"
        else:
            ratio = 0
            status = "TACHYONIC"

        print(f"  {N:>5} {top:>9.4f} {gauge:>9.4f} {self_:>9.4f} {total:>9.4f} "
              f"{mH_sq:>8.4f} {ratio:>8.4f} {status:>12}")

    print(f"\n  Tree level:  m_H/m_W = {1/np.sqrt(2):.4f} (= 1/sqrt(2))")
    print(f"  Observed:    m_H/m_W = 1.558")

    # Sensitivity analysis
    print(f"\n  {'='*60}")
    print(f"  SENSITIVITY ANALYSIS (N=64)")
    print(f"  {'='*60}")

    print(f"\n  Varying lambda (Higgs self-coupling):")
    for lam in [0.13, 0.25, 0.5, 1.0, 2.0]:
        top, gauge, self_, total = total_correction(64, lam=lam)
        mH_sq = 1.0 + total
        ratio = np.sqrt(max(mH_sq, 0) / 0.105) if mH_sq > 0 else 0
        sign = '+' if total > 0 else '-'
        print(f"    lam={lam:.2f}: total={total:>+8.4f} ({sign}), m_H/m_W={ratio:.4f}")

    print(f"\n  Varying g^2 (gauge coupling):")
    for g_sq in [0.2, 0.42, 0.65, 1.0]:
        top, gauge, self_, total = total_correction(64, g_sq=g_sq)
        mH_sq = 1.0 + total
        ratio = np.sqrt(max(mH_sq, 0) / 0.105) if mH_sq > 0 else 0
        print(f"    g^2={g_sq:.2f}: total={total:>+8.4f}, m_H/m_W={ratio:.4f}")

    # THE ANSWER
    print(f"\n  {'='*60}")
    print(f"  VERDICT")
    print(f"  {'='*60}")

    top, gauge, self_, total = total_correction(256)
    mH_sq = 1.0 + total

    if total > 0:
        print(f"\n  TOTAL CORRECTION IS POSITIVE: delta_mH^2 = {total:+.4f}")
        ratio = np.sqrt(mH_sq / 0.105)
        print(f"  m_H/m_W = {ratio:.4f} (up from 0.707)")
        if ratio > 1.0:
            print(f"  MOVED TOWARD 1.558! Partial success.")
        print(f"  Key: our lambda=1/2 (4x SM) -> Higgs self-loop DOMINATES.")
    elif total < 0:
        print(f"\n  TOTAL CORRECTION IS NEGATIVE: delta_mH^2 = {total:+.4f}")
        if mH_sq > 0:
            ratio = np.sqrt(mH_sq / 0.105)
            print(f"  m_H/m_W = {ratio:.4f} (DOWN from {1/np.sqrt(2):.4f})")
        else:
            print(f"  m_H^2 < 0: TACHYONIC (Higgs VEV destabilized)")
        print(f"  Top loop dominates even with our enhanced self-coupling.")
        print(f"  HONEST: hierarchy problem persists at one-loop.")
    else:
        print(f"\n  CORRECTIONS CANCEL: delta = 0.")

    # Component analysis
    print(f"\n  Component analysis (N=256):")
    print(f"    Top (y_t=1, N_c=3):   {top:>+9.4f}  (NEGATIVE)")
    print(f"    Gauge (3 bosons):     {gauge:>+9.4f}  (positive)")
    print(f"    Higgs self (lam=1/2): {self_:>+9.4f}  (positive)")
    print(f"    TOTAL:                {total:>+9.4f}")
    print(f"    |top| vs gauge+self:  {abs(top):.4f} vs {gauge+self_:.4f}")


if __name__ == '__main__':
    main()
