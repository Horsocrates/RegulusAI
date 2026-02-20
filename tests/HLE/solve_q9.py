# Q9: Generating sets of free products
# d(G) = min generating set size
# A = A_5 (alternating group on 5 letters, |A_5| = 60)
# B_n = A_5^n (direct product of n copies)
# C_n = free product of 50 copies of B_n
# Find largest n such that d(C_n) <= 100

# By Grushko's theorem: d(G1 * G2 * ... * Gk) = d(G1) + d(G2) + ... + d(Gk)
# So d(C_n) = 50 * d(B_n) = 50 * d(A_5^n)
# Need: 50 * d(A_5^n) <= 100, i.e., d(A_5^n) <= 2

# Question: what is the largest n such that A_5^n is 2-generated?

# For a non-abelian finite simple group S, the max n such that S^n is 2-generated
# is given by m_2(S) = phi_2(S) / |Aut(S)|
# where phi_2(S) = number of ordered generating pairs of S

# For A_5:
# |A_5| = 60
# |Aut(A_5)| = |S_5| = 120
# phi_2(A_5) = number of ordered pairs (a,b) in A_5 x A_5 that generate A_5

# Count non-generating pairs by inclusion-exclusion over maximal subgroups
# Maximal subgroups of A_5:
# 1. A_4 (order 12) - 5 conjugates (point stabilizers)
# 2. D_5 = Dih(Z_5) (order 10) - 6 conjugates
# 3. S_3 (order 6) = Dih(Z_3) - 10 conjugates

# Inclusion-exclusion on the lattice of subgroups
# Non-generating pairs = pairs contained in some proper subgroup

# Need to know intersections of maximal subgroups
# A_4 ∩ A_4: stabilizer of two points = S_2 x S_1 ∩ A_5 ...
# This gets complicated. Let me just enumerate computationally.

# Generate A_5 as permutations of {0,1,2,3,4}
from itertools import permutations

def perm_compose(p, q):
    """Compose permutations: (p∘q)(i) = p(q(i))"""
    return tuple(p[q[i]] for i in range(len(p)))

def perm_inverse(p):
    inv = [0] * len(p)
    for i, v in enumerate(p):
        inv[v] = i
    return tuple(inv)

def perm_sign(p):
    """Return sign of permutation: +1 for even, -1 for odd"""
    n = len(p)
    visited = [False] * n
    sign = 1
    for i in range(n):
        if not visited[i]:
            cycle_len = 0
            j = i
            while not visited[j]:
                visited[j] = True
                j = p[j]
                cycle_len += 1
            if cycle_len % 2 == 0:
                sign *= -1
    return sign

# Generate all even permutations of {0,1,2,3,4}
identity = tuple(range(5))
A5 = [p for p in permutations(range(5)) if perm_sign(p) == 1]
print(f"|A_5| = {len(A5)}")

# Encode permutations as integers for faster lookup
perm_to_idx = {p: i for i, p in enumerate(A5)}
idx_to_perm = A5

def generates_A5(a, b, max_iter=60):
    """Check if elements a, b generate A_5"""
    generated = set()
    to_process = [a, b]
    generated.add(a)
    generated.add(b)

    while to_process:
        new = []
        for g in to_process:
            for h in list(generated):
                for prod in [perm_compose(g, h), perm_compose(h, g)]:
                    if prod not in generated:
                        generated.add(prod)
                        new.append(prod)
                        if len(generated) == 60:
                            return True
        to_process = new
        if not new:
            break
    return len(generated) == 60

# Count generating pairs
print("Counting generating pairs of A_5...")
phi_2 = 0
total = 0
for i, a in enumerate(A5):
    for b in A5:
        total += 1
        if generates_A5(a, b):
            phi_2 += 1
    if i % 10 == 0:
        print(f"  Progress: {i+1}/60 elements done...")

print(f"\nphi_2(A_5) = {phi_2}")
print(f"|Aut(A_5)| = |S_5| = 120")
m2 = phi_2 // 120  # integer division (should divide evenly for simple groups)
print(f"m_2(A_5) = phi_2 / |Aut(A_5)| = {phi_2} / 120 = {m2}")
print(f"\nLargest n such that d(A_5^n) <= 2: n = {m2}")
print(f"Largest n such that d(C_n) <= 100: n = {m2}")
