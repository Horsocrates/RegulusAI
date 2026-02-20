from math import gcd, comb

q = 12740347

def gl_order(n, s):
    if n == 0: return 1
    r = 1
    for i in range(n):
        r *= (s**n - s**i)
    return r

def mult_order(base, p):
    b = base % p
    if b == 0: return None
    order, current = 1, b
    while current != 1:
        current = (current * b) % p
        order += 1
    return order

def count_order_p_SL3(s, p):
    d = mult_order(s, p)
    if d is None or d > 3: return 0
    r = (p - 1) // d
    gl3 = gl_order(3, s)

    if d == 2:
        c = gl3 // ((s-1) * gl_order(1, s**2))
        return r * c
    elif d == 3:
        c = gl3 // gl_order(1, s**3)
        return r * c

    # d = 1
    c3 = gl3 // (s-1)**3
    c21 = gl3 // (gl_order(2,s) * (s-1))
    total = (p-1) // 2 * c3 + (p-1) * c21 + (p-1) * (p-5) // 6 * c3
    return total

def count_order_p_SL4(fq, p):
    d = mult_order(fq, p)
    if d is None or d > 4: return 0
    r = (p - 1) // d
    gl4 = gl_order(4, fq)

    if d == 2:
        t1 = r * gl4 // (gl_order(2, fq) * gl_order(1, fq**2))
        t2 = r * gl4 // gl_order(2, fq**2)
        t3 = comb(r, 2) * gl4 // gl_order(1, fq**2)**2
        return t1 + t2 + t3
    elif d == 3:
        c = gl4 // ((fq-1) * gl_order(1, fq**3))
        return r * c
    elif d == 4:
        c = gl4 // gl_order(1, fq**4)
        return r * c

    # d = 1
    C_211 = gl4 // (gl_order(2, fq) * (fq-1)**2)
    C_121 = gl4 // ((fq-1) * gl_order(2, fq) * (fq-1))
    C_1111 = gl4 // (fq-1)**4
    C_031 = gl4 // (gl_order(3, fq) * (fq-1))
    C_022 = gl4 // gl_order(2, fq)**2
    C_0211 = gl4 // (gl_order(2, fq) * (fq-1)**2)
    C_01111 = gl4 // (fq-1)**4

    t1 = (p-1) // 2 * C_211
    t2 = (p-1) * C_121
    t3 = (p-1) * (p-5) // 6 * C_1111
    t4 = (p-1) * C_031
    t5 = (p-1) // 2 * C_022
    t6 = (p-1) * (p-5) // 2 * C_0211

    # 4 distinct eigenvalues from Zp* with sum = 0 mod p (unordered)
    ordered_4 = (p-1) * (p*p - 9*p + 26)
    n4 = ordered_4 // 24
    t7 = n4 * C_01111

    total = t1 + t2 + t3 + t4 + t5 + t6 + t7
    return total

s = q**2
primes_both = [2, 3, 5, 7, 13, 19, 37, 43, 67, 163, 1801, 146921, 707797, 3185087, 12740347, 110478721]

print("=== Checking primes ===")
for p in primes_both:
    if p == q:
        print(f"p={p}: EQUAL (both q^12-1)")
        continue
    if p == 2:
        c1 = s**2 * (s**2 + s + 1)
        c2 = q**4 * (q**4 + q**2 + 1)
        print(f"p=2: EQUAL={c1==c2}")
        continue
    if p == 3:
        print(f"p=3: NOT EQUAL (computed earlier)")
        continue

    c_psl3 = count_order_p_SL3(s, p)
    c_psl4 = count_order_p_SL4(q, p)
    d3 = mult_order(s, p)
    d4 = mult_order(q, p)
    eq = c_psl3 == c_psl4
    print(f"p={p}: d(q^2,p)={d3}, d(q,p)={d4}, EQUAL={eq}")
    if not eq:
        print(f"  PSL3={c_psl3}")
        print(f"  PSL4={c_psl4}")
