"""
Exhaustive analysis of finite string rewriting rules x -> y
on alphabet {a, b} with |x|, |y| <= 3.

A substitution x -> y is "finite" (terminating) if for ANY initial word
and ANY sequence of applications, only finitely many steps can be performed.

Equivalently, it's finite iff there's no infinite derivation sequence.
"""
from itertools import product

def gen_words(max_len=3):
    """Generate all words of length <= max_len on {a,b}, including empty."""
    words = ['']  # empty word
    for length in range(1, max_len + 1):
        for w in product('ab', repeat=length):
            words.append(''.join(w))
    return words

def apply_rule(word, x, y):
    """Return all possible single-step results of applying x->y to word."""
    if not x:
        return set()  # empty x: substitution doesn't make sense in standard rewriting
    results = set()
    for i in range(len(word) - len(x) + 1):
        if word[i:i+len(x)] == x:
            new_word = word[:i] + y + word[i+len(x):]
            results.add(new_word)
    return results

def is_finite_bfs(x, y, max_len=30, max_states=5000):
    """
    Check if x -> y is finite by BFS from all starting words.

    Strategy: We try to find an infinite derivation.
    If |y| < |x|: always finite (length decreases).
    If |y| = |x|: length preserved, finite state space for each length.
    If |y| > |x|: length can grow; we bound the search.

    For |y| > |x|: we start from x itself and small words containing x,
    and see if derivations keep going or terminate.
    """
    lx = len(x)
    ly = len(y)

    if not x:
        return True  # empty pattern: no match possible in standard sense

    if x == y:
        return True  # identity: trivially finite (though arguably not a "substitution")

    # If |y| < |x|: each step reduces length. Always finite.
    if ly < lx:
        return True

    # If |y| = |x|: length is preserved. For a fixed length, there are finitely many strings.
    # We need to check: can we cycle? If no cycle, then finite.
    # Check all strings up to some reasonable length.
    if ly == lx:
        # For same-length rules, check if there's a cycle reachable from any string
        # We check strings of various lengths
        for start_len in range(lx, max_len + 1):
            # Generate all strings of this length that contain x
            for start_word in gen_words_of_length(start_len):
                if x not in start_word:
                    continue
                visited = set()
                queue = [start_word]
                visited.add(start_word)
                cycle_found = False
                while queue:
                    current = queue.pop(0)
                    nexts = apply_rule(current, x, y)
                    for nw in nexts:
                        if nw in visited:
                            # We reached a previously visited state -> cycle!
                            cycle_found = True
                            break
                        visited.add(nw)
                        queue.append(nw)
                    if cycle_found:
                        return False
                    if len(visited) > max_states:
                        break
        return True  # No cycle found

    # |y| > |x|: length grows. This is the tricky case.
    # Check if from small starting words, derivations terminate.
    # Start from x itself, and all words up to length 6 that contain x.

    for start_len in range(lx, min(8, max_len) + 1):
        for start_word in gen_words_of_length(start_len):
            if x not in start_word:
                continue
            visited = set()
            queue = [start_word]
            visited.add(start_word)
            found_long = False
            while queue:
                current = queue.pop(0)
                if len(current) > max_len:
                    # Growing without bound -> not finite
                    return False
                nexts = apply_rule(current, x, y)
                for nw in nexts:
                    if nw not in visited:
                        visited.add(nw)
                        queue.append(nw)
                if len(visited) > max_states:
                    # Too many states explored, likely not finite
                    return False
    return True


def gen_words_of_length(n):
    """Generate all words of exactly length n on {a,b}."""
    if n == 0:
        return ['']
    return [''.join(w) for w in product('ab', repeat=n)]


def is_finite_smart(x, y):
    """
    Smarter analysis combining theoretical results with BFS verification.
    """
    if not x:
        return True
    if x == y:
        return True

    lx, ly = len(x), len(y)

    # Case 1: |y| < |x| -> always finite
    if ly < lx:
        return True

    # Case 2: |y| = |x| -> need to check for cycles
    if ly == lx:
        return is_same_length_finite(x, y)

    # Case 3: |y| > |x| -> need careful analysis
    return is_growing_finite(x, y)


def is_same_length_finite(x, y):
    """
    Check if same-length rule x -> y is finite.
    Same length means the string length never changes.
    For a fixed starting length n, there are 2^n possible strings.
    The rule is finite iff there are no cycles in the rewrite graph
    for any string length.

    Key insight: if we can define a strict total order that decreases
    with each application, it's finite.

    For same-length x -> y:
    - If we interpret strings as binary numbers (a=0, b=1),
      replacing x by y changes the number.
    - If y > x numerically, every replacement increases the number.
      But different replacement positions might increase by different amounts.
    - The key: does every single-step replacement increase (or decrease)
      the numerical value? If so, finite.

    Actually for same-length replacements, replacing at any position:
    The change in value = (val(y) - val(x)) * 2^(n - i - lx)
    where i is the position. Since val(y) != val(x) and 2^k > 0,
    the sign of the change is always the same: sign(val(y) - val(x)).
    So if val(y) > val(x), every replacement increases the number -> finite.
    If val(y) < val(x), every replacement decreases the number -> finite.

    Wait, this is always the case when x != y and |x| = |y|!
    So ALL same-length substitutions with x != y are finite!

    Hmm wait, that's not quite right. The numerical value argument:
    If we have string w = w[0..i-1] x w[i+lx..n-1]
    and replace x by y at position i:
    w' = w[0..i-1] y w[i+lx..n-1]

    val(w') - val(w) = sum over j in [0,lx): (y[j] - x[j]) * 2^(n-1-i-j)

    This equals (val(y) - val(x)) * 2^(n-1-i-lx+1) ... no wait.

    Let me think again. Using a=0, b=1:
    val(w) = sum_{k=0}^{n-1} w[k] * 2^{n-1-k}

    The substring at position i has contribution:
    sum_{j=0}^{lx-1} w[i+j] * 2^{n-1-i-j}
    = 2^{n-1-i} * sum_{j=0}^{lx-1} w[i+j] * 2^{-j}

    When we replace x by y (same length), the change is:
    sum_{j=0}^{lx-1} (y[j] - x[j]) * 2^{n-1-i-j}
    = 2^{n-1-i-(lx-1)} * sum_{j=0}^{lx-1} (y[j] - x[j]) * 2^{lx-1-j}

    The sum S = sum_{j=0}^{lx-1} (y[j]-x[j]) * 2^{lx-1-j} = val(y) - val(x)

    So the change = (val(y) - val(x)) * 2^{n-i-lx}

    Since val(y) != val(x) (because y != x), the sign of the change is
    always sign(val(y) - val(x)), independent of position i.

    So the numerical value strictly increases (or decreases) with each step.
    Since the value is bounded in [0, 2^n - 1], this is finite!

    Therefore ALL same-length x -> y with x != y are finite.
    """
    return True  # All same-length rules are finite!


def is_growing_finite(x, y):
    """
    Check if rule x -> y with |y| > |x| is finite.

    Key observation: if x appears as a substring of y, then:
    Starting from word x, apply the rule: x -> y. Now y contains x,
    so we can apply again, getting a longer word. This gives an infinite
    derivation. So NOT finite.

    If x does NOT appear in y: does applying x -> y to some word w
    create new occurrences of x? This can happen at the boundary
    between y and the surrounding context.

    More precisely: can we find w containing x such that replacing
    one occurrence of x by y creates a new occurrence of x
    (overlapping the boundary)?

    If so, this new occurrence can be replaced, potentially creating more,
    leading to an infinite derivation.

    This is the subtle case requiring careful analysis.
    """
    lx, ly = len(x), len(y)

    # If x is substring of y, definitely not finite
    if x in y:
        return False

    # Use BFS to check termination from various starting words
    # Since |y| > |x|, strings grow. If we can keep applying, it's infinite.

    # Start from small words containing x and see if derivation terminates
    max_word_len = 40  # if strings grow beyond this, assume infinite
    max_states = 10000

    for start_len in range(lx, min(lx + 4, 8) + 1):
        for start_word in gen_words_of_length(start_len):
            if x not in start_word:
                continue

            visited = set()
            queue = [start_word]
            visited.add(start_word)

            while queue:
                current = queue.pop(0)
                nexts = apply_rule(current, x, y)
                for nw in nexts:
                    if len(nw) > max_word_len:
                        return False  # Unbounded growth
                    if nw not in visited:
                        visited.add(nw)
                        queue.append(nw)
                if len(visited) > max_states:
                    return False  # Too many states, likely infinite

    return True


def main():
    words = gen_words(3)
    print(f"Words of length <= 3: {words}")
    print(f"Count: {len(words)}")

    nonempty = [w for w in words if w]
    print(f"Nonempty words: {nonempty}")
    print(f"Count: {len(nonempty)}")

    # Count substitutions
    # x must be nonempty (replacing empty string is ill-defined)
    # y can be anything (including empty = deletion)
    # x != y (otherwise not really a substitution, or trivially finite)

    pairs = [(x, y) for x in nonempty for y in words if x != y]
    print(f"\nTotal substitution pairs (x nonempty, x!=y): {len(pairs)}")

    # Also try: all pairs including x=y
    pairs_all = [(x, y) for x in nonempty for y in words]
    print(f"Total substitution pairs (x nonempty, any y): {len(pairs_all)}")

    # The problem says 255. Let me check various countings
    print(f"\n15*15 = {15*15}")
    print(f"15*15-15 = {15*15-15}")
    print(f"14*15 = {14*15}")
    print(f"14*15-14 = {14*15-14}")
    print(f"15*17 = {15*17}")
    print(f"14*15+14*3 = {14*15+14*3}")  # random

    # Now check each pair for finiteness
    print("\n=== Checking finiteness of all substitutions ===")

    finite_count = 0
    infinite_count = 0
    finite_rules = []
    infinite_rules = []

    for x, y in pairs:
        if is_finite_smart(x, y):
            finite_count += 1
            finite_rules.append((x, y))
        else:
            infinite_count += 1
            infinite_rules.append((x, y))

    print(f"\nResults (x nonempty, x != y, total = {len(pairs)}):")
    print(f"Finite: {finite_count}")
    print(f"Infinite: {infinite_count}")

    # Break down by (|x|, |y|)
    print("\n=== Breakdown by (|x|, |y|) ===")
    for lx in range(1, 4):
        for ly in range(0, 4):
            finite_in_cat = sum(1 for x, y in finite_rules if len(x) == lx and len(y) == ly)
            infinite_in_cat = sum(1 for x, y in infinite_rules if len(x) == lx and len(y) == ly)
            total_in_cat = finite_in_cat + infinite_in_cat
            if total_in_cat > 0:
                print(f"  |x|={lx}, |y|={ly}: {total_in_cat} total, {finite_in_cat} finite, {infinite_in_cat} infinite")

    print("\n=== Infinite rules ===")
    for x, y in infinite_rules:
        print(f"  '{x}' -> '{y}' (|x|={len(x)}, |y|={len(y)})")

    # If we include x=y as trivially finite
    print(f"\n=== If we add x=y pairs (trivially finite): ===")
    identity_pairs = [(x, x) for x in nonempty]
    print(f"Identity pairs: {len(identity_pairs)}")
    print(f"Total finite (including identity): {finite_count + len(identity_pairs)}")
    print(f"Total pairs: {len(pairs) + len(identity_pairs)}")


if __name__ == '__main__':
    main()
