"""
Deep verification: do ab->baa etc. truly have INFINITE derivations?
Or just very long finite ones?

Key test: from a starting word, does BFS EVER terminate?
If it terminates (all words eventually have no x), it's finite.
If words keep growing forever, it's infinite.

The question is: can growth be truly unbounded?
For ab->baa: each application replaces 'ab' (len 2) with 'baa' (len 3), +1.
If the number of 'ab' occurrences stays >= 1, the word grows without bound.

Analysis: replacing 'ab' at position i with 'baa':
- The 'a' from 'ab' becomes 'b' (moved left) + 'aa'
- New word has the 'a' from position i+1 duplicated

Let's check: does replacing one 'ab' by 'baa' always preserve at least one 'ab'?
Not necessarily. E.g., 'ab' -> 'baa' (no 'ab' left). Done in 1 step.
'aab' -> 'abaa' (has 'ab'). 'abaa' -> 'baaaa' (no 'ab'). Done in 2 steps.

But from 'aaab': 'aaab' -> 'aabaa' (has 'ab'). 'aabaa' -> 'ababaa' or 'aababa' or ...
This could branch and some branches may be longer.

The question for FINITENESS: is there a starting word w such that from w,
there is a CHOICE of replacements that goes on forever?

Let's check by tracking the maximum length of the derivation tree.
"""
from itertools import product
from collections import deque

def gen_words_of_length(n):
    if n == 0:
        return ['']
    return [''.join(w) for w in product('ab', repeat=n)]

def apply_rule_all(word, x, y):
    results = set()
    for i in range(len(word) - len(x) + 1):
        if word[i:i+len(x)] == x:
            new_word = word[:i] + y + word[i+len(x):]
            results.add(new_word)
    return results


def max_derivation_length(start, x, y, depth_limit=200, state_limit=50000):
    """
    Compute the maximum number of steps in any derivation from start.
    Returns (max_depth, terminated_normally).
    If we hit the depth_limit, return (depth_limit, False).
    """
    # DFS with memoization: for each word, the max depth from it
    cache = {}

    def dfs(word, depth):
        if depth > depth_limit:
            return depth, False
        if word in cache:
            return cache[word], True

        nexts = apply_rule_all(word, x, y)
        if not nexts:
            cache[word] = 0
            return 0, True

        max_d = 0
        all_term = True
        for nw in nexts:
            if len(nw) > 100:
                return depth_limit + 1, False
            d, term = dfs(nw, depth + 1)
            if d > max_d:
                max_d = d
            if not term:
                all_term = False
                break

        result = max_d + 1
        if all_term:
            cache[word] = result
        return result, all_term

    return dfs(start, 0)


def full_bfs_termination(start, x, y, max_len=200, max_states=200000):
    """
    Full BFS from start. Returns:
    - 'finite' if all derivations terminate
    - 'infinite' if word length exceeds max_len
    - 'unknown' if we hit the state limit
    """
    visited = set()
    queue = deque([start])
    visited.add(start)
    max_word_len = len(start)

    while queue:
        current = queue.popleft()
        nexts = apply_rule_all(current, x, y)
        for nw in nexts:
            if len(nw) > max_len:
                return 'infinite', max_word_len, len(visited)
            if nw not in visited:
                visited.add(nw)
                queue.append(nw)
                if len(nw) > max_word_len:
                    max_word_len = len(nw)
        if len(visited) > max_states:
            return 'unknown', max_word_len, len(visited)

    return 'finite', max_word_len, len(visited)


def main():
    # Test the four tricky rules
    rules = [
        ('ab', 'baa'),
        ('ab', 'bba'),
        ('ba', 'aab'),
        ('ba', 'abb'),
    ]

    for x, y in rules:
        print(f"\n{'='*60}")
        print(f"Rule: '{x}' -> '{y}'")
        print(f"{'='*60}")

        # Check from starting words of increasing length
        found_infinite = False
        for start_len in range(len(x), 16):
            if found_infinite:
                break
            for sw in gen_words_of_length(start_len):
                if x not in sw:
                    continue

                result, max_wl, n_states = full_bfs_termination(
                    sw, x, y, max_len=150, max_states=100000
                )

                if result == 'infinite':
                    print(f"  start='{sw}' (len={start_len}): INFINITE (max_word_len={max_wl}, states={n_states})")
                    found_infinite = True
                    break
                elif result == 'unknown':
                    print(f"  start='{sw}' (len={start_len}): UNKNOWN (max_word_len={max_wl}, states={n_states})")
                elif result == 'finite' and max_wl > start_len + 3:
                    print(f"  start='{sw}' (len={start_len}): finite (max_word_len={max_wl}, states={n_states})")

        if not found_infinite:
            print(f"  All checked starting words terminated!")

    # Now let me understand the mechanism for ab->baa being infinite
    print(f"\n{'='*60}")
    print(f"Detailed mechanism for 'ab' -> 'baa'")
    print(f"{'='*60}")

    # The key insight: what starting word leads to unbounded growth?
    # Let's try a^n b for various n
    for n in range(1, 12):
        sw = 'a' * n + 'b'
        result, max_wl, n_states = full_bfs_termination(
            sw, 'ab', 'baa', max_len=200, max_states=50000
        )
        print(f"  a^{n}b = '{sw}': {result} (max_word_len={max_wl}, states={n_states})")

    # Try a^n b^m for various n, m
    print("\n  a^n b^m patterns:")
    for n in range(1, 8):
        for m in range(1, 8):
            sw = 'a' * n + 'b' * m
            result, max_wl, n_states = full_bfs_termination(
                sw, 'ab', 'baa', max_len=200, max_states=50000
            )
            if result != 'finite' or max_wl > len(sw) + 5:
                print(f"  a^{n}b^{m} = '{sw}': {result} (max_word_len={max_wl}, states={n_states})")

    # Now I want to understand: is ab->baa truly infinite or just very long?
    # If the maximum derivation depth grows faster than any polynomial in start length,
    # it's probably infinite. Let me track exact max depths for small examples.
    print(f"\n  Exact max derivation depths for 'ab' -> 'baa':")
    for n in range(1, 9):
        sw = 'a' * n + 'b'
        d, term = max_derivation_length(sw, 'ab', 'baa', depth_limit=500, state_limit=100000)
        status = "terminated" if term else "EXCEEDED LIMIT"
        print(f"  a^{n}b: max_depth={d}, {status}")

    print(f"\n  Exact max derivation depths for a^n b^2:")
    for n in range(1, 9):
        sw = 'a' * n + 'bb'
        d, term = max_derivation_length(sw, 'ab', 'baa', depth_limit=500, state_limit=100000)
        status = "terminated" if term else "EXCEEDED LIMIT"
        print(f"  a^{n}bb: max_depth={d}, {status}")


if __name__ == '__main__':
    main()
