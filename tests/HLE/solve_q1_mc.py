# Monte Carlo verification for Q1, d=2 and d=3
import numpy as np
import math

for d in [1, 2, 3, 4]:
    N = 500000
    volumes = []
    avg_dists = []

    for _ in range(N):
        axes = np.random.randint(0, d, size=d)
        ts = np.random.uniform(-1, 1, size=d)
        points = np.zeros((d, d))
        for i in range(d):
            points[i, axes[i]] = ts[i]

        if d == 1:
            vol = abs(points[0, 0])
        else:
            vol = abs(np.linalg.det(points)) / math.factorial(d)
        volumes.append(vol)

        all_pts = np.vstack([np.zeros(d), points])
        dists = []
        for i in range(d + 1):
            for j in range(i + 1, d + 1):
                dists.append(np.linalg.norm(all_pts[i] - all_pts[j]))
        avg_dists.append(np.mean(dists))

    V_mc = np.mean(volumes)
    E_mc = np.mean(avg_dists)
    R_mc = V_mc / E_mc
    print(f"d={d}: V_mc={V_mc:.6f}, E_mc={E_mc:.6f}, R_mc={R_mc:.6f}")

# Expected analytical values
E_sqrt2 = (np.sqrt(2) + np.log(1 + np.sqrt(2))) / 3
print(f"\nAnalytical E[sqrt(T1^2+T2^2)] = {E_sqrt2:.6f}")
print(f"Analytical V_1=0.5, V_2={1/16}, V_3={1/216:.6f}, V_4={1/4096:.8f}")

# Compute analytical E_d for d=1,2,3,4
for d in [1,2,3,4]:
    V_d = 1.0 / (2*d)**d
    n_pairs = d*(d+1)//2
    sum_origin = d * 0.5
    n_pp = d*(d-1)//2
    if n_pp > 0:
        E_pair = (1/d) * (2/3) + ((d-1)/d) * E_sqrt2
        sum_points = n_pp * E_pair
    else:
        sum_points = 0
    E_d = (sum_origin + sum_points) / n_pairs
    R_d = V_d / E_d
    print(f"d={d}: V_d={V_d:.8f}, E_d={E_d:.8f}, R_d={R_d:.8f}")
