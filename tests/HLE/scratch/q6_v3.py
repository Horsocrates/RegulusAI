from itertools import product

def gen_words(max_len):
    words = ['']
    for length in range(1, max_len + 1):
        for combo in product('ab', repeat=length):
            words.append(''.join(combo))
    return words

def is_finite(x, y):
    """Determine if one-rule string rewriting {x -> y} terminates."""
    if x == y:
        return True  # no actual change
    if x == '':
        return y == ''  # inserting y is infinite if y != ''
    if len(y) < len(x):
        return True  # word strictly shrinks
    if len(y) == len(x):
        # THEOREM: All same-length one-rule systems on binary alphabet terminate.
        # Proof: Let k be the first position where x and y differ.
        # Each application changes char at some position from x[k] to y[k].
        # This strictly changes the binary encoding of the word in one direction.
        # (The change at position k dominates all changes at later positions.)
        return True

    # len(y) > len(x): word grows. Check for non-termination.
    # Since length strictly increases each step, no cycles possible.
    # System is infinite iff some starting word leads to arbitrarily long words
    # all containing x.
    # BFS: explore all reachable words. If word exceeds length bound, INFINITE.

    max_wlen = 30
    for start_len in range(len(x), len(x) + 8):
        for start_combo in product('ab', repeat=start_len):
            sw = ''.join(start_combo)
            if x not in sw:
                continue
            # BFS from sw
            visited = {sw}
            frontier = [sw]
            while frontier:
                nxt = []
                for w in frontier:
                    start = 0
                    while True:
                        p = w.find(x, start)
                        if p == -1:
                            break
                        nw = w[:p] + y + w[p+len(x):]
                        if len(nw) > max_wlen:
                            return False  # unbounded growth with x persisting
                        if nw not in visited:
                            visited.add(nw)
                            if x in nw:
                                nxt.append(nw)
                        start = p + 1
                frontier = nxt
    return True

words = gen_words(3)
print(f"Total words: {len(words)}, Total pairs: {len(words)**2}")

finite_count = 0
details = {'|y|<|x|': [0,0], '|y|=|x|': [0,0], '|y|>|x|': [0,0], 'x=y': [0,0], 'x=empty': [0,0]}

for x in words:
    for y in words:
        fin = is_finite(x, y)
        if fin:
            finite_count += 1

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
        details[cat][0 if fin else 1] += 1

print(f"\nFinite: {finite_count}")
print(f"Infinite: {len(words)**2 - finite_count}")

print("\nBy category (finite, infinite):")
for cat, (f, i) in sorted(details.items()):
    print(f"  {cat}: {f} finite, {i} infinite, total {f+i}")

# List length-increasing finite cases
print("\nFinite cases with |y| > |x|:")
for x in words:
    for y in words:
        if x != '' and x != y and len(y) > len(x) and is_finite(x, y):
            print(f"  '{x}' -> '{y}'")
