"""
Definitive analysis: Check ALL growing rules with very thorough BFS.
The key question: which growing rules (|y| > |x|) are truly finite?

We now know ab->baa IS infinite (from length 9 starting words).
Need to recheck ALL growing rules with longer starting words.
"""
from itertools import product
from collections import deque

def gen_words_of_length(n):
    if n == 0:
        return ['']
    return [''.join(w) for w in product('ab', repeat=n)]

def gen_words(max_len=3):
    words = ['']
    for length in range(1, max_len + 1):
        for w in product('ab', repeat=length):
            words.append(''.join(w))
    return words

def apply_rule_all(word, x, y):
    results = set()
    for i in range(len(word) - len(x) + 1):
        if word[i:i+len(x)] == x:
            new_word = word[:i] + y + word[i+len(x):]
            results.add(new_word)
    return results

def is_finite_very_thorough(x, y, verbose=False):
    """
    Very thorough check: BFS from all starting words up to length 12+.
    """
    lx, ly = len(x), len(y)

    if not x or x == y:
        return True
    if ly < lx:
        return True
    if ly == lx:
        return True

    # Growing: check from starting words up to length lx+10
    max_start_len = min(lx + 10, 14)
    max_word_len = 200
    max_states = 200000

    for start_len in range(lx, max_start_len + 1):
        for start_word in gen_words_of_length(start_len):
            if x not in start_word:
                continue

            visited = set()
            queue = deque([start_word])
            visited.add(start_word)

            while queue:
                current = queue.popleft()
                nexts = apply_rule_all(current, x, y)
                for nw in nexts:
                    if len(nw) > max_word_len:
                        if verbose:
                            print(f"  INFINITE from '{start_word}' (len={start_len}): word grew to >{max_word_len}")
                        return False
                    if nw not in visited:
                        visited.add(nw)
                        queue.append(nw)
                if len(visited) > max_states:
                    if verbose:
                        print(f"  LIKELY INFINITE from '{start_word}' (len={start_len}): >{max_states} states")
                    return False

    return True


def main():
    words = gen_words(3)
    nonempty = [w for w in words if w]

    print("=== DEFINITIVE COUNT OF FINITE SUBSTITUTIONS ===\n")

    # All growing rules
    growing_rules = []
    for x in nonempty:
        for y in words:
            if x == y:
                continue
            if len(y) > len(x):
                growing_rules.append((x, y))

    print(f"Total growing rules: {len(growing_rules)}")

    finite_growing = []
    infinite_growing = []

    for x, y in growing_rules:
        is_fin = is_finite_very_thorough(x, y, verbose=True)
        if is_fin:
            finite_growing.append((x, y))
        else:
            infinite_growing.append((x, y))

    print(f"\nFinite growing: {len(finite_growing)}")
    for x, y in finite_growing:
        print(f"  '{x}' -> '{y}'")

    print(f"\nInfinite growing: {len(infinite_growing)}")
    for x, y in infinite_growing:
        print(f"  '{x}' -> '{y}' (x in y: {x in y})")

    # Now compute total
    print(f"\n{'='*60}")
    print(f"COMPLETE CLASSIFICATION")
    print(f"{'='*60}")

    # Shrinking rules (|y| < |x|): always finite
    shrinking = [(x,y) for x in nonempty for y in words if x != y and len(y) < len(x)]
    same_length = [(x,y) for x in nonempty for y in words if x != y and len(y) == len(x)]

    print(f"\nShrinking (|y| < |x|): {len(shrinking)} - ALL FINITE")
    print(f"Same-length (|y| = |x|): {len(same_length)} - ALL FINITE")
    print(f"Growing (|y| > |x|): {len(growing_rules)} total")
    print(f"  Finite: {len(finite_growing)}")
    print(f"  Infinite: {len(infinite_growing)}")

    total_finite = len(shrinking) + len(same_length) + len(finite_growing)
    total_infinite = len(infinite_growing)
    total = len(shrinking) + len(same_length) + len(growing_rules)

    print(f"\nTOTAL (x nonempty, x != y): {total}")
    print(f"TOTAL FINITE: {total_finite}")
    print(f"TOTAL INFINITE: {total_infinite}")

    # With identity rules
    n_identity = len(nonempty)  # 14
    print(f"\nWith identity (x=y): +{n_identity} (all trivially finite)")
    print(f"TOTAL (x nonempty, any y): {total + n_identity}")
    print(f"TOTAL FINITE (including identity): {total_finite + n_identity}")

    # Check the 255 puzzle again
    # The problem says 255 substitutions. Let me list all our rules and count.
    print(f"\n--- Breakdown ---")
    for lx in range(1, 4):
        for ly in range(0, 4):
            s = [(x,y) for x,y in shrinking if len(x)==lx and len(y)==ly]
            sl = [(x,y) for x,y in same_length if len(x)==lx and len(y)==ly]
            fg = [(x,y) for x,y in finite_growing if len(x)==lx and len(y)==ly]
            ig = [(x,y) for x,y in infinite_growing if len(x)==lx and len(y)==ly]
            t = len(s) + len(sl) + len(fg) + len(ig)
            f = len(s) + len(sl) + len(fg)
            if t > 0:
                print(f"  |x|={lx}, |y|={ly}: total={t}, finite={f}, infinite={len(ig)}")


if __name__ == '__main__':
    main()
