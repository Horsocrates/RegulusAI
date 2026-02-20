# Q2: ODE blow-up
# x' = -3xy, y' = -y^2 - x + 1
# x(0) > 1. For what y(0) does the solution blow up?

import numpy as np

def rk4_step(f, t, u, h):
    k1 = f(t, u)
    k2 = f(t + h/2, u + h/2 * k1)
    k3 = f(t + h/2, u + h/2 * k2)
    k4 = f(t + h, u + h * k3)
    return u + h/6 * (k1 + 2*k2 + 2*k3 + k4)

def system(t, u):
    x, y = u
    return np.array([-3*x*y, -y**2 - x + 1])

def test_blowup(x0, y0, T=10, h=0.0005):
    u = np.array([x0, y0], dtype=float)
    t = 0.0
    while t < T:
        u = rk4_step(system, t, u, h)
        t += h
        if abs(u[1]) > 1e6 or abs(u[0]) > 1e10:
            return True, t
        if np.isnan(u[0]) or np.isnan(u[1]):
            return True, t
    return False, T

# Test various y(0) values for different x(0) > 1
print("Testing blow-up for x(0) > 1:")
print("="*60)

for x0 in [1.5, 2.0, 5.0]:
    print(f"\nx(0) = {x0}:")
    for y0 in np.arange(-3, 4, 0.5):
        bu, t_end = test_blowup(x0, y0, T=15)
        label = f"BLOW-UP at t={t_end:.3f}" if bu else "bounded"
        print(f"  y(0)={y0:6.2f}: {label}")

# Fine-grained search for transition
print("\n\nFine search for x0=2.0:")
for y0 in np.arange(-0.5, 1.5, 0.1):
    bu, t_end = test_blowup(2.0, y0, T=20)
    label = f"BLOW-UP at t={t_end:.3f}" if bu else "bounded"
    print(f"  y(0)={y0:6.2f}: {label}")

# Bisection to find critical y0 for x0=2
print("\n\nBisection for x0=2.0:")
lo, hi = -1.0, 5.0
for _ in range(60):
    mid = (lo + hi) / 2
    bu, _ = test_blowup(2.0, mid, T=30)
    if bu:
        lo = mid
    else:
        hi = mid
print(f"  Critical y(0) ~ {(lo+hi)/2:.10f}")

# Try x0=1.5
print("\nBisection for x0=1.5:")
lo, hi = -1.0, 5.0
for _ in range(60):
    mid = (lo + hi) / 2
    bu, _ = test_blowup(1.5, mid, T=30)
    if bu:
        lo = mid
    else:
        hi = mid
print(f"  Critical y(0) ~ {(lo+hi)/2:.10f}")

# Try x0=5
print("\nBisection for x0=5:")
lo, hi = -1.0, 20.0
for _ in range(60):
    mid = (lo + hi) / 2
    bu, _ = test_blowup(5.0, mid, T=30)
    if bu:
        lo = mid
    else:
        hi = mid
print(f"  Critical y(0) ~ {(lo+hi)/2:.10f}")

# Try x0=1.01
print("\nBisection for x0=1.01:")
lo, hi = -1.0, 5.0
for _ in range(60):
    mid = (lo + hi) / 2
    bu, _ = test_blowup(1.01, mid, T=50, h=0.001)
    if bu:
        lo = mid
    else:
        hi = mid
print(f"  Critical y(0) ~ {(lo+hi)/2:.10f}")
