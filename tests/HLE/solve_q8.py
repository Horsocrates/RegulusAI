# Q8: Scanner coverage optimization
# Room: 140 x 110 m
# C2: circle r=20m, cost=20000
# C1: circle r=5m (diameter 10m), cost=1600
# R1: square 10m side, cost=2000
# Coverage >= 0.88, minimize total cost
# Scanner centers at multiples of 5m

import numpy as np

W, H = 140, 110
TOTAL_AREA = W * H  # 15400
REQUIRED = 0.88 * TOTAL_AREA  # 13552

# Discretize room into 1m x 1m cells
# Cell (i,j) represents the 1x1 square centered at (i+0.5, j+0.5) for i in [0,W), j in [0,H)

# Possible scanner positions: multiples of 5 within room
# x in {0, 5, 10, ..., 140}, y in {0, 5, 10, ..., 110}
positions_x = list(range(0, W+1, 5))  # 0 to 140 step 5: 29 values
positions_y = list(range(0, H+1, 5))  # 0 to 110 step 5: 23 values

print(f"Room: {W}x{H} = {TOTAL_AREA} m^2")
print(f"Required coverage: {REQUIRED} m^2 ({REQUIRED/TOTAL_AREA*100:.1f}%)")
print(f"Grid positions: {len(positions_x)} x {len(positions_y)} = {len(positions_x)*len(positions_y)}")

# For each scanner type and position, precompute coverage (set of cells)
# Use 1m resolution for accuracy

def c2_coverage(cx, cy):
    """Circle radius 20m centered at (cx, cy)"""
    cells = set()
    r = 20
    for i in range(max(0, int(cx-r)), min(W, int(cx+r)+1)):
        for j in range(max(0, int(cy-r)), min(H, int(cy+r)+1)):
            # Cell center at (i+0.5, j+0.5)
            dx = i + 0.5 - cx
            dy = j + 0.5 - cy
            if dx*dx + dy*dy <= r*r:
                cells.add((i, j))
    return cells

def c1_coverage(cx, cy):
    """Circle radius 5m centered at (cx, cy)"""
    cells = set()
    r = 5
    for i in range(max(0, int(cx-r)), min(W, int(cx+r)+1)):
        for j in range(max(0, int(cy-r)), min(H, int(cy+r)+1)):
            dx = i + 0.5 - cx
            dy = j + 0.5 - cy
            if dx*dx + dy*dy <= r*r:
                cells.add((i, j))
    return cells

def r1_coverage(cx, cy):
    """Square 10m side centered at (cx, cy)"""
    cells = set()
    half = 5
    for i in range(max(0, int(cx-half)), min(W, int(cx+half))):
        for j in range(max(0, int(cy-half)), min(H, int(cy+half))):
            cells.add((i, j))
    return cells

# First, find a good C2-only solution
# C2 is most cost-effective per area: 20000 / (pi*400) = 15.92 $/m^2
# C1: 1600 / (pi*25) = 20.37 $/m^2
# R1: 2000 / 100 = 20.00 $/m^2

print("\nCost per m^2 (standalone, no edge effects):")
print(f"  C2: {20000/(np.pi*400):.2f} $/m^2")
print(f"  C1: {1600/(np.pi*25):.2f} $/m^2")
print(f"  R1: {2000/100:.2f} $/m^2")

# Greedy approach: try different numbers of C2 scanners
# For each configuration, fill remaining with cheapest small scanners

# First try: how many C2 scanners needed for 88% coverage alone?
# Place C2 in a grid pattern that maximizes coverage

# C2 radius 20m. The room is 140x110.
# Try different C2 placements

best_cost = float('inf')
best_config = None

# Strategy 1: Only C2 scanners, try to cover 88%
# Try placing C2 on a coarser grid
print("\n--- Strategy: C2 only ---")
for dx in [25, 30, 35, 40, 45]:
    for dy in [25, 30, 35, 40, 45]:
        for ox in range(0, dx, 5):
            for oy in range(0, dy, 5):
                covered = set()
                n_scanners = 0
                for cx in range(ox, W+1, dx):
                    if cx not in range(0, W+1):
                        continue
                    for cy in range(oy, H+1, dy):
                        if cy not in range(0, H+1):
                            continue
                        covered |= c2_coverage(cx, cy)
                        n_scanners += 1
                coverage_frac = len(covered) / TOTAL_AREA
                cost = n_scanners * 20000
                if coverage_frac >= 0.88 and cost < best_cost:
                    best_cost = cost
                    best_config = f"C2 grid dx={dx} dy={dy} ox={ox} oy={oy}, n={n_scanners}"
                    print(f"  {best_config}: coverage={coverage_frac:.4f}, cost={cost}")

print(f"\nBest C2-only: cost={best_cost}, config={best_config}")

# Strategy 2: Fewer C2 + fill with C1 or R1
print("\n--- Strategy: C2 + C1/R1 fill ---")
# Try some specific C2 configurations and fill with cheapest option
for dx in [30, 35, 40, 45, 50]:
    for dy in [30, 35, 40, 45, 50]:
        for ox in range(0, min(dx, 25), 5):
            for oy in range(0, min(dy, 25), 5):
                covered = set()
                c2_count = 0
                for cx in range(ox, W+1, dx):
                    for cy in range(oy, H+1, dy):
                        covered |= c2_coverage(cx, cy)
                        c2_count += 1

                coverage = len(covered) / TOTAL_AREA
                c2_cost = c2_count * 20000

                if coverage >= 0.88:
                    total_cost = c2_cost
                    if total_cost < best_cost:
                        best_cost = total_cost
                        best_config = f"C2 grid dx={dx} dy={dy}, n_c2={c2_count}, coverage={coverage:.4f}"
                        print(f"  {best_config}, cost={total_cost}")
                else:
                    # Fill remaining with R1 (cheapest per area among small scanners)
                    needed = int(np.ceil(REQUIRED)) - len(covered)
                    if needed > 0:
                        # Greedy fill with C1 (cheapest small scanner)
                        # Each R1 covers up to 100 new cells, C1 covers up to ~78 new cells
                        # Cost per new cell: R1 = 2000/100 = 20, C1 = 1600/78.5 = 20.4
                        # R1 is cheaper per area... but C1 is cheaper absolute
                        # For filling gaps, use C1 (1600 each, ~78 m^2)
                        fill_count = int(np.ceil(needed / 78.5))  # rough estimate with C1
                        fill_cost_c1 = fill_count * 1600
                        fill_count_r1 = int(np.ceil(needed / 100))
                        fill_cost_r1 = fill_count_r1 * 2000
                        fill_cost = min(fill_cost_c1, fill_cost_r1)
                        total_cost = c2_cost + fill_cost
                        if total_cost < best_cost:
                            best_cost = total_cost
                            best_config = f"C2(n={c2_count})+fill({needed}m^2), C2 grid dx={dx} dy={dy}"
                            print(f"  {best_config}, cost~{total_cost}")

print(f"\nBest overall: cost={best_cost}")
print(f"Config: {best_config}")
