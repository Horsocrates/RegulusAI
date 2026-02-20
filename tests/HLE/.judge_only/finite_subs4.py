"""
Verification of tricky growing cases where x is NOT a substring of y.
These are: ab->baa, ab->bba, ba->aab, ba->abb
Also verify all finite growing rules are truly finite.
"""
from itertools import product
from collections import deque

def gen_words_of_length(n):
    if n == 0:
        return ['']
    return [''.join(w) for w in product('ab', repeat=n)]

def apply_rule_all(word, x, y):
    """Return all possible single-step results."""
    results = set()
    for i in range(len(word) - len(x) + 1):
        if word[i:i+len(x)] == x:
            new_word = word[:i] + y + word[i+len(x):]
            results.add(new_word)
    return results

def trace_derivation(word, x, y, max_steps=20, max_len=100):
    """Show derivation tree (BFS) from a starting word."""
    visited = {word}
    queue = deque([(word, 0)])
    print(f"  Start: '{word}'")

    while queue:
        current, depth = queue.popleft()
        if depth >= max_steps:
            continue
        nexts = apply_rule_all(current, x, y)
        for nw in sorted(nexts):
            tag = ""
            if nw in visited:
                tag = " (already seen)"
            elif len(nw) > max_len:
                tag = " (TOO LONG)"
            if nw not in visited and len(nw) <= max_len:
                visited.add(nw)
                queue.append((nw, depth + 1))
            if depth < 6:
                print(f"  {'  ' * (depth+1)}'{current}' -> '{nw}'{tag}")

    return visited


def is_truly_finite(x, y, max_len=100, max_states=100000):
    """Very thorough check with large bounds."""
    if not x or x == y:
        return True, 0
    if len(y) < len(x):
        return True, 0
    if len(y) == len(x):
        return True, 0

    # Growing: BFS from all starting words of length up to lx+8
    lx = len(x)
    total_visited = 0
    for start_len in range(lx, min(lx + 8, 14) + 1):
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
                    if len(nw) > max_len:
                        return False, total_visited + len(visited)
                    if nw not in visited:
                        visited.add(nw)
                        queue.append(nw)
                if len(visited) > max_states:
                    return False, total_visited + len(visited)

            total_visited += len(visited)

    return True, total_visited


def main():
    print("=== Verifying tricky infinite cases ===\n")

    tricky_cases = [
        ('ab', 'baa'),
        ('ab', 'bba'),
        ('ba', 'aab'),
        ('ba', 'abb'),
    ]

    for x, y in tricky_cases:
        print(f"\n--- Rule: '{x}' -> '{y}' ---")
        print(f"x in y: {x in y}")

        # Try starting from various words
        for start_len in range(2, 10):
            for sw in gen_words_of_length(start_len):
                if x not in sw:
                    continue
                # Quick check: does derivation grow?
                visited = {sw}
                queue = deque([sw])
                max_seen_len = len(sw)
                steps = 0
                while queue and steps < 500:
                    current = queue.popleft()
                    for nw in apply_rule_all(current, x, y):
                        if nw not in visited:
                            visited.add(nw)
                            queue.append(nw)
                            if len(nw) > max_seen_len:
                                max_seen_len = len(nw)
                    steps += 1
                    if max_seen_len > 50:
                        print(f"  From '{sw}': GROWS to len {max_seen_len} in {steps} steps, {len(visited)} states")
                        break

                if max_seen_len > 50:
                    # Show the growth path
                    print(f"  Tracing from '{sw}':")
                    trace_derivation(sw, x, y, max_steps=8, max_len=60)
                    break
            else:
                continue
            break

    print("\n\n=== Verifying finite growing rules are TRULY finite ===\n")

    finite_growing = [
        ('a', 'bb'), ('a', 'bbb'),
        ('b', 'aa'), ('b', 'aaa'),
        ('aa', 'aba'), ('aa', 'abb'), ('aa', 'bab'), ('aa', 'bba'), ('aa', 'bbb'),
        ('ab', 'aaa'), ('ab', 'bbb'),
        ('ba', 'aaa'), ('ba', 'bbb'),
        ('bb', 'aaa'), ('bb', 'aab'), ('bb', 'aba'), ('bb', 'baa'), ('bb', 'bab'),
    ]

    for x, y in finite_growing:
        is_fin, total = is_truly_finite(x, y, max_len=150, max_states=200000)
        status = "FINITE" if is_fin else "INFINITE!"
        print(f"  '{x}' -> '{y}': {status} (explored {total} states)")

    # Verify a -> bb more carefully
    print("\n=== Special verification: 'a' -> 'bb' ===")
    print("Starting from 'a': a -> bb. 'bb' has no 'a'. Done.")
    print("Starting from 'aa': aa -> bba or abb. Neither contains 'a'. Done.")
    print("Starting from 'aba': aba -> bbba, abbb, abba. None contain 'a'... wait, abba contains 'a'!")
    print("  abba -> bbbba, abbbb. Neither contains 'a'. Done.")
    print("Key: replacing a by bb doubles the replacement. But since bb contains no a,")
    print("each step removes one 'a' and inserts 'bb'. Eventually all a's are gone.")
    print("But wait: bb doesn't contain 'a', so each step reduces count of 'a' by 1.")
    print("Since count of 'a' is non-negative and decreases by 1 each step, finite.")
    print("Actually: the result of replacing 'a' by 'bb' cannot contain 'a' at the replacement site.")
    print("The surrounding context still has its original 'a's, but we replaced one.")
    print("So #a decreases by 1 each step. Finite!")

    # Verify aa -> aba: x not in y, but boundary overlaps exist
    print("\n=== Special verification: 'aa' -> 'aba' ===")
    print("x='aa', y='aba'. 'aa' not in 'aba'. Left overlap at k=1: y[:1]='a'=x[1:]='a'. YES.")
    print("So if context before is '...a', then '...a' + 'aba' = '...aaba' which contains 'aa'!")
    print("Let's trace:")
    trace_derivation('aaa', 'aa', 'aba', max_steps=6, max_len=50)
    print()
    trace_derivation('aaaa', 'aa', 'aba', max_steps=6, max_len=50)
    print()
    print("Hmm, does this terminate? Each step replaces 'aa' by 'aba' (len 2 -> 3, +1).")
    print("But the number of 'a' characters stays the same (aa has 2 a's, aba has 2 a's + 1 b).")
    print("Actually: aa has 2 a's, aba has 2 a's. So #a is preserved, but #b increases by 1.")
    print("The number of overlapping 'aa' pairs can only decrease as b's get inserted between a's.")
    print("Eventually no more 'aa' exists. So FINITE.")

    # Verify ab -> baa: this was flagged as infinite
    print("\n=== Special verification: 'ab' -> 'baa' ===")
    print("x='ab', y='baa'. 'ab' not in 'baa'.")
    print("Left overlap k=1: x[1:]='b', y[:1]='b'. YES! So if '...a' precedes, '...a'+'baa'='...abaa' contains 'ab'.")
    print("Right overlap m=1: y[-1:]='a', x[:1]='a'. YES! So if 'b...' follows, 'baa'+'b...'='baab...' contains 'ab'.")
    print("So both boundaries can create new 'ab's!")

    trace_derivation('ab', 'ab', 'baa', max_steps=10, max_len=40)
    print()
    trace_derivation('aab', 'ab', 'baa', max_steps=6, max_len=40)
    print()
    trace_derivation('abb', 'ab', 'baa', max_steps=6, max_len=40)
    print()
    trace_derivation('aabb', 'ab', 'baa', max_steps=6, max_len=60)

    # Check: does the NUMBER of ab's increase?
    print("\n  Counting 'ab' occurrences in derivations from 'aabb':")
    word = 'aabb'
    visited = {word}
    queue = deque([(word, 0)])
    while queue:
        current, depth = queue.popleft()
        if depth >= 5:
            continue
        nexts = apply_rule_all(current, 'ab', 'baa')
        for nw in sorted(nexts):
            count_ab = sum(1 for i in range(len(nw)-1) if nw[i:i+2] == 'ab')
            print(f"    depth={depth+1}: '{nw}' has {count_ab} 'ab's, len={len(nw)}")
            if nw not in visited:
                visited.add(nw)
                queue.append((nw, depth + 1))


if __name__ == '__main__':
    main()
