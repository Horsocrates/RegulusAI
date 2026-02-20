"""
Deep analysis of finite string rewriting rules.
Focus on the growing rules where x is NOT a substring of y.
These are the subtle cases where boundary effects matter.
"""
from itertools import product
from collections import deque

def gen_words_of_length(n):
    if n == 0:
        return ['']
    return [''.join(w) for w in product('ab', repeat=n)]

def apply_rule(word, x, y):
    """Return all possible single-step results of applying x->y to word."""
    results = set()
    for i in range(len(word) - len(x) + 1):
        if word[i:i+len(x)] == x:
            new_word = word[:i] + y + word[i+len(x):]
            results.add(new_word)
    return results

def check_rule_detailed(x, y, max_len=80, max_states=50000, verbose=False):
    """
    Very thorough BFS check.
    Returns (is_finite, evidence)
    """
    lx, ly = len(x), len(y)

    if not x or x == y:
        return True, "trivial"
    if ly < lx:
        return True, "length decreasing"
    if ly == lx:
        return True, "same length, monotone numerical value"

    # |y| > |x|: growing rule
    # Start from x itself and words of length up to lx+4
    for start_len in range(lx, min(lx + 6, 12) + 1):
        for start_word in gen_words_of_length(start_len):
            if x not in start_word:
                continue

            visited = set()
            queue = deque([start_word])
            visited.add(start_word)

            while queue:
                current = queue.popleft()
                nexts = apply_rule(current, x, y)
                for nw in nexts:
                    if len(nw) > max_len:
                        if verbose:
                            print(f"    Unbounded growth from '{start_word}': reached len {len(nw)}")
                        return False, f"unbounded growth from '{start_word}'"
                    if nw not in visited:
                        visited.add(nw)
                        queue.append(nw)
                if len(visited) > max_states:
                    if verbose:
                        print(f"    Too many states from '{start_word}': {len(visited)}")
                    return False, f"too many states from '{start_word}'"

    return True, "BFS terminated"


def boundary_creates_x(x, y):
    """
    Check if replacing x by y can create a new occurrence of x at the boundary.
    We need to check: for some prefix A and suffix B of surrounding context,
    does A + y + B contain x where x overlaps with A or B?

    More precisely: after replacing ...AxB... -> ...AyB..., is there an occurrence
    of x in AyB that wasn't in AxB (other than the one we replaced)?

    The new occurrences can only be those that overlap with y (since the A and B
    parts haven't changed).
    """
    lx, ly = len(x), len(y)

    # An occurrence of x in the result AyB overlaps with y if it starts in
    # A (within lx-1 chars of the boundary) or if it starts in y and extends into B.

    # Check: for each possible amount of overlap, does y's prefix/suffix
    # combined with surrounding characters form x?

    # Left boundary: x starts in A and ends in y.
    # x = A_suffix + y_prefix, where A_suffix has length k (1 <= k <= min(lx-1, possible))
    # So x[k:] = y[:lx-k] and x[:k] can be anything (it's from A)
    # For this to happen, we need y to start with x[k:lx] for some k in 1..lx-1.
    left_overlaps = []
    for k in range(1, lx):
        suffix_of_x = x[k:]  # What A_suffix looks like (part of x)
        prefix_of_y_needed = x[k:]
        if y[:len(prefix_of_y_needed)] == prefix_of_y_needed:
            left_overlaps.append(k)

    # Right boundary: x starts in y and ends in B.
    # x = y_suffix + B_prefix, where y_suffix has length m, B_prefix has length lx-m
    # So x[:m] = y[ly-m:] for some m in 1..lx-1
    right_overlaps = []
    for m in range(1, lx):
        if y[ly-m:] == x[:m]:
            right_overlaps.append(m)

    # Also: x entirely within y (substring)
    x_in_y = x in y

    return left_overlaps, right_overlaps, x_in_y


def main():
    # Focus on growing rules (|y| > |x|) with x not in y
    # These are the boundary cases

    words_by_len = {}
    for l in range(0, 4):
        words_by_len[l] = gen_words_of_length(l)

    nonempty_words = []
    for l in range(1, 4):
        nonempty_words.extend(words_by_len[l])

    all_words = [''] + nonempty_words

    print("=== Detailed analysis of ALL growing rules ===\n")

    all_growing = []
    for x in nonempty_words:
        for y in all_words:
            if x == y:
                continue
            if len(y) <= len(x):
                continue
            all_growing.append((x, y))

    print(f"Total growing rules: {len(all_growing)}")

    finite_growing = []
    infinite_growing = []

    for x, y in all_growing:
        is_fin, reason = check_rule_detailed(x, y, max_len=80, max_states=50000, verbose=False)
        if is_fin:
            finite_growing.append((x, y, reason))
        else:
            infinite_growing.append((x, y, reason))

    print(f"Finite growing: {len(finite_growing)}")
    print(f"Infinite growing: {len(infinite_growing)}")

    print("\n--- Finite growing rules ---")
    for x, y, reason in finite_growing:
        lo, ro, xiny = boundary_creates_x(x, y)
        print(f"  '{x}' -> '{y}': {reason}, x_in_y={xiny}, left_overlaps={lo}, right_overlaps={ro}")

    print("\n--- Infinite growing rules where x NOT in y ---")
    for x, y, reason in infinite_growing:
        if x not in y:
            lo, ro, xiny = boundary_creates_x(x, y)
            print(f"  '{x}' -> '{y}': {reason}, left_overlaps={lo}, right_overlaps={ro}")

            # Show a sample derivation
            print(f"    Sample derivation from '{x}':")
            current = x
            for step in range(8):
                nexts = apply_rule(current, x, y)
                if not nexts:
                    print(f"    Step {step}: '{current}' -> (no more x)")
                    break
                next_word = min(nexts, key=len)  # pick shortest
                print(f"    Step {step}: '{current}' -> '{next_word}'")
                current = next_word
                if len(current) > 60:
                    print(f"    ... (growing)")
                    break

    # Now count ALL finite substitutions
    print("\n\n=== COMPLETE COUNT ===")

    total_finite = 0
    total_infinite = 0
    total = 0

    categories = {}

    for x in nonempty_words:
        for y in all_words:
            if x == y:
                continue
            total += 1
            lx, ly = len(x), len(y)
            cat = f"|x|={lx},|y|={ly}"

            if ly < lx:
                is_fin = True
                reason = "shrinking"
            elif ly == lx:
                is_fin = True
                reason = "same-length"
            else:
                is_fin, reason = check_rule_detailed(x, y, max_len=80, max_states=50000)

            if cat not in categories:
                categories[cat] = {'finite': 0, 'infinite': 0, 'total': 0}
            categories[cat]['total'] += 1

            if is_fin:
                total_finite += 1
                categories[cat]['finite'] += 1
            else:
                total_infinite += 1
                categories[cat]['infinite'] += 1

    print(f"\nTotal substitutions (x nonempty, x!=y): {total}")
    print(f"Finite: {total_finite}")
    print(f"Infinite: {total_infinite}")

    print("\nBy category:")
    for cat in sorted(categories.keys()):
        d = categories[cat]
        print(f"  {cat}: total={d['total']}, finite={d['finite']}, infinite={d['infinite']}")

    # Different total conventions:
    print(f"\n--- With identity (x=y) counted as finite ---")
    n_identity = len(nonempty_words)  # 14
    print(f"Identity rules: {n_identity}")
    print(f"Total finite: {total_finite + n_identity}")
    print(f"Total: {total + n_identity}")

    # What if we also count empty -> y for nonempty y?
    # empty -> y for nonempty y: these can't actually apply (where would we replace empty?)
    # But maybe they're counted as finite?
    # empty -> nonempty y: 14 rules
    # empty -> empty: 1 rule
    print(f"\n--- With empty -> y rules ---")
    # empty -> y for any y (including empty): 15 rules
    # All trivially finite (no occurrences of empty to replace, or identity)
    # Actually empty -> y is problematic: empty string occurs everywhere
    # So it's NOT finite unless y is also empty
    # But conventionally, x must be nonempty for string rewriting

    print(f"\n--- Trying 255 interpretation ---")
    # One more try: words length <= 3, including empty: 15
    # Pairs (x,y): both from all 15 words, x != y: 15*14 = 210
    # Hmm, that's still 210.

    # What if the problem counts distinct substitution FUNCTIONS, not pairs?
    # Some pairs might give the same substitution function?
    # E.g., if x doesn't appear in any string, the substitution does nothing.
    # But on infinite alphabet, every x appears somewhere.
    # On {a,b}*, every nonempty x over {a,b} appears in some word.
    # So all pairs give distinct substitutions.

    # I'm going to accept that 255 might be from a different counting convention
    # and report the answer proportionally or just report my count.

    # BUT WAIT: maybe the problem says "length ≤ 3" meaning the PAIR has
    # combined length ≤ 3, or max(|x|,|y|) ≤ 3, or something else?
    # "Consider all possible couples (x,y) of words of length ≤ 3"
    # This should mean each of x and y is a word of length ≤ 3.

    # Let me count one more way: what if "words" means NONEMPTY words?
    # Then there are 2+4+8=14 words, and "(we allow for the empty word)"
    # means the empty word IS additionally allowed for y only.
    # Then x: 14 words, y: 15 words (14 + empty), x != y: 14*15 - 14 = 196
    # Hmm, 196. Still not 255.

    # OR: x: 14, y: 15, including x=y: 14*15 = 210.

    # I THINK the problem may have a typo or different convention.
    # Let me just be clear about my answer.

    print(f"\n{'='*60}")
    print(f"FINAL ANSWER")
    print(f"{'='*60}")
    print(f"Out of {total} substitutions (x nonempty, y any, x!=y):")
    print(f"  FINITE: {total_finite}")
    print(f"  INFINITE: {total_infinite}")
    print(f"Including x=y identity rules (trivially finite):")
    print(f"  FINITE: {total_finite + n_identity} out of {total + n_identity}")


if __name__ == '__main__':
    main()
