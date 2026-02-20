# Q8: Precise greedy optimization
import numpy as np

W, H = 140, 110
TOTAL_AREA = W * H
REQUIRED = int(np.ceil(0.88 * TOTAL_AREA))  # 13552

# Precompute coverage for each scanner type at each position
positions = [(x, y) for x in range(0, W+1, 5) for y in range(0, H+1, 5)]

def get_coverage(cx, cy, scanner_type):
    cells = set()
    if scanner_type == 'C2':
        r = 20
        for i in range(max(0, cx-r), min(W, cx+r+1)):
            for j in range(max(0, cy-r), min(H, cy+r+1)):
                if (i+0.5-cx)**2 + (j+0.5-cy)**2 <= r*r:
                    cells.add((i, j))
    elif scanner_type == 'C1':
        r = 5
        for i in range(max(0, cx-r), min(W, cx+r+1)):
            for j in range(max(0, cy-r), min(H, cy+r+1)):
                if (i+0.5-cx)**2 + (j+0.5-cy)**2 <= r*r:
                    cells.add((i, j))
    elif scanner_type == 'R1':
        half = 5
        for i in range(max(0, cx-half), min(W, cx+half)):
            for j in range(max(0, cy-half), min(H, cy+half)):
                cells.add((i, j))
    return cells

# Greedy: place C2 first (most cost-effective), then fill with C1/R1
print("Greedy C2 placement:")
covered = set()
c2_placed = []
costs = {'C2': 20000, 'C1': 1600, 'R1': 2000}

# Place C2 scanners greedily
for step in range(20):
    best_gain = 0
    best_pos = None
    for cx, cy in positions:
        cov = get_coverage(cx, cy, 'C2')
        gain = len(cov - covered)
        if gain > best_gain:
            best_gain = gain
            best_pos = (cx, cy)
    if best_gain == 0 or len(covered) >= REQUIRED:
        break
    cx, cy = best_pos
    new_cov = get_coverage(cx, cy, 'C2')
    covered |= new_cov
    c2_placed.append(best_pos)
    coverage_pct = len(covered) / TOTAL_AREA * 100
    print(f"  C2 #{len(c2_placed)} at ({cx},{cy}): +{best_gain} cells, total={len(covered)} ({coverage_pct:.1f}%)")
    if coverage_pct >= 88:
        break

c2_cost = len(c2_placed) * 20000
print(f"\nC2 scanners: {len(c2_placed)}, cost={c2_cost}")
print(f"Coverage after C2: {len(covered)}/{TOTAL_AREA} = {len(covered)/TOTAL_AREA*100:.2f}%")

# If not enough, fill with C1 (cheapest per unit)
if len(covered) < REQUIRED:
    c1_placed = []
    for step in range(200):
        best_gain = 0
        best_pos = None
        best_type = None
        # Try both C1 and R1
        for stype, cost in [('C1', 1600), ('R1', 2000)]:
            for cx, cy in positions:
                cov = get_coverage(cx, cy, stype)
                gain = len(cov - covered)
                # Cost effectiveness: cost per new cell
                if gain > 0:
                    eff = cost / gain
                    if best_pos is None or eff < best_gain:
                        best_gain = eff
                        best_pos = (cx, cy)
                        best_type = stype
        if best_pos is None:
            break
        cx, cy = best_pos
        new_cov = get_coverage(cx, cy, best_type)
        actual_gain = len(new_cov - covered)
        covered |= new_cov
        c1_placed.append((best_pos, best_type))
        if len(covered) >= REQUIRED:
            break

    fill_cost = sum(costs[t] for _, t in c1_placed)
    print(f"Fill scanners: {len(c1_placed)}")
    for pos, t in c1_placed[:10]:
        print(f"  {t} at {pos}")
    if len(c1_placed) > 10:
        print(f"  ... and {len(c1_placed)-10} more")
    print(f"Fill cost: {fill_cost}")
    total_cost = c2_cost + fill_cost
else:
    total_cost = c2_cost
    fill_cost = 0

print(f"\nTotal cost (greedy): {total_cost}")
print(f"Coverage: {len(covered)}/{TOTAL_AREA} = {len(covered)/TOTAL_AREA*100:.2f}%")

# Now try: what if we use fewer C2 and more small scanners?
# Or more C2 and no small?
print("\n\n--- Trying different C2 counts ---")
for target_c2 in range(8, 16):
    covered2 = set()
    c2_list = []
    for step in range(target_c2):
        best_gain = 0
        best_pos = None
        for cx, cy in positions:
            cov = get_coverage(cx, cy, 'C2')
            gain = len(cov - covered2)
            if gain > best_gain:
                best_gain = gain
                best_pos = (cx, cy)
        if best_gain == 0:
            break
        covered2 |= get_coverage(best_pos[0], best_pos[1], 'C2')
        c2_list.append(best_pos)

    c2_cost2 = len(c2_list) * 20000
    remaining = max(0, REQUIRED - len(covered2))

    # Fill with cheapest (greedy C1/R1)
    fill_cost2 = 0
    fill_covered = set(covered2)
    fill_count = 0
    while len(fill_covered) < REQUIRED:
        best_eff = float('inf')
        best_pos = None
        best_type = None
        for stype, cost in [('C1', 1600), ('R1', 2000)]:
            for cx, cy in positions:
                cov = get_coverage(cx, cy, stype)
                gain = len(cov - fill_covered)
                if gain > 0:
                    eff = cost / gain
                    if eff < best_eff:
                        best_eff = eff
                        best_pos = (cx, cy)
                        best_type = stype
        if best_pos is None:
            break
        fill_covered |= get_coverage(best_pos[0], best_pos[1], best_type)
        fill_cost2 += costs[best_type]
        fill_count += 1

    total2 = c2_cost2 + fill_cost2
    cov_pct = len(fill_covered) / TOTAL_AREA * 100
    print(f"  {len(c2_list)} C2 + {fill_count} fill: cost={total2}, coverage={cov_pct:.1f}%")
