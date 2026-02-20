from itertools import product

def gen_words(max_len):
    words = ['']
    for length in range(1, max_len + 1):
        for combo in product('ab', repeat=length):
            words.append(''.join(combo))
    return words

def is_finite(x, y, max_wlen=25, max_steps=500):
    if x == y:
        return True  # no actual change
    if x == '':
        return y == ''
    if len(y) < len(x):
        return True

    for start_len in range(len(x), min(len(x) + 8, max_wlen + 1)):
        for start_combo in product('ab', repeat=start_len):
            sw = ''.join(start_combo)
            if x not in sw:
                continue
            visited = {sw}
            frontier = [sw]
            steps = 0
            while frontier and steps < max_steps:
                nxt = []
                for w in frontier:
                    start = 0
                    while True:
                        p = w.find(x, start)
                        if p == -1:
                            break
                        nw = w[:p] + y + w[p+len(x):]
                        if len(nw) > max_wlen:
                            return False
                        if nw in visited:
                            if x in nw:
                                return False
                        else:
                            visited.add(nw)
                            if x in nw:
                                nxt.append(nw)
                        start = p + 1
                frontier = nxt
                steps += 1
            if steps >= max_steps:
                return False
    return True

words = gen_words(3)
print(f"Total words: {len(words)}, Total pairs: {len(words)**2}")

finite_count = 0
finite_interesting = []  # |y| >= |x| and x != y
for x in words:
    for y in words:
        if is_finite(x, y):
            finite_count += 1
            if x != y and len(y) >= len(x) and x != '':
                finite_interesting.append((x, y))

print(f"\nFinite: {finite_count}")
print(f"Infinite: {len(words)**2 - finite_count}")

# Count by category
cat_counts = {}
for x in words:
    for y in words:
        if x == y:
            cat = 'x=y'
        elif x == '':
            cat = 'x=empty'
        elif len(y) < len(x):
            cat = '|y|<|x|'
        elif len(y) == len(x):
            cat = '|y|=|x|'
        else:
            cat = '|y|>|x|'
        fin = is_finite(x, y)
        key = (cat, fin)
        cat_counts[key] = cat_counts.get(key, 0) + 1

print("\nBy category:")
for (cat, fin), cnt in sorted(cat_counts.items()):
    print(f"  {cat}, finite={fin}: {cnt}")

print(f"\nInteresting finite cases (|y| >= |x|, x!=y, x!=''):")
for x, y in sorted(finite_interesting):
    print(f"  '{x}' -> '{y}'")
