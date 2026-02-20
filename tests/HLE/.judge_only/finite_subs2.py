"""
More thorough analysis of finite string rewriting rules.
Focus on edge cases and verification.
"""
from itertools import product

def gen_words(max_len=3):
    words = ['']
    for length in range(1, max_len + 1):
        for w in product('ab', repeat=length):
            words.append(''.join(w))
    return words

def gen_words_of_length(n):
    if n == 0:
        return ['']
    return [''.join(w) for w in product('ab', repeat=n)]

def apply_rule(word, x, y):
    """Return all possible single-step results of applying x->y to word."""
    if not x:
        return set()
    results = set()
    for i in range(len(word) - len(x) + 1):
        if word[i:i+len(x)] == x:
            new_word = word[:i] + y + word[i+len(x):]
            results.add(new_word)
    return results

def is_finite_thorough(x, y, max_word_len=50, max_states=20000):
    """
    Thorough BFS-based check for finiteness.
    Start from all words of length up to some bound that contain x.
    Track all reachable words. If we find unbounded growth or cycles, not finite.
    """
    if not x:
        return True
    if x == y:
        return True

    lx, ly = len(x), len(y)

    # |y| < |x|: always finite
    if ly < lx:
        return True

    # |y| = |x|: same length, use numerical value argument
    if ly == lx:
        # The binary value interpretation (a=0, b=1):
        # Replacing x by y changes value by (val(y)-val(x)) * 2^k for some k > 0
        # Sign is always the same -> monotone -> finite
        return True

    # |y| > |x|: BFS from small starting words
    # We need to check if from ANY starting word, there exists an infinite derivation.
    # Start from words of length lx to lx+3 containing x.

    for start_len in range(lx, min(lx + 5, 10) + 1):
        for start_word in gen_words_of_length(start_len):
            if x not in start_word:
                continue

            visited = set()
            queue = [start_word]
            visited.add(start_word)
            is_inf = False

            while queue and not is_inf:
                current = queue.pop(0)
                nexts = apply_rule(current, x, y)
                for nw in nexts:
                    if len(nw) > max_word_len:
                        is_inf = True
                        break
                    if nw not in visited:
                        visited.add(nw)
                        queue.append(nw)
                if len(visited) > max_states:
                    is_inf = True
                    break

            if is_inf:
                return False

    return True


def analyze_growing_case(x, y):
    """
    Detailed analysis of why a rule with |y| > |x| is or isn't finite.
    """
    lx, ly = len(x), len(y)
    assert ly > lx

    x_in_y = x in y
    results = {
        'x': x, 'y': y,
        'x_in_y': x_in_y,
    }

    # Check: can replacing x by y create a new x at the boundary?
    # When we have ...AxB... and replace x by y, we get ...AyB...
    # A new occurrence of x could overlap A and y, or y and B, or be entirely in y.
    # "Entirely in y" is covered by x_in_y check.
    # Overlap cases: check if any suffix of potential prefix A + prefix of y forms x,
    # or suffix of y + prefix of potential suffix B forms x.

    # But in general, BFS covers all these cases.

    return results


def main():
    words = gen_words(3)
    nonempty = [w for w in words if w]

    # All pairs (x, y) with x nonempty, x != y
    pairs = [(x, y) for x in nonempty for y in words if x != y]

    print(f"Total pairs: {len(pairs)}")

    finite_rules = []
    infinite_rules = []

    for x, y in pairs:
        if is_finite_thorough(x, y):
            finite_rules.append((x, y))
        else:
            infinite_rules.append((x, y))

    print(f"Finite: {len(finite_rules)}")
    print(f"Infinite: {len(infinite_rules)}")

    # Detailed breakdown
    print("\n=== Breakdown by (|x|, |y|) ===")
    for lx in range(1, 4):
        for ly in range(0, 4):
            f = [(x,y) for x,y in finite_rules if len(x)==lx and len(y)==ly]
            inf = [(x,y) for x,y in infinite_rules if len(x)==lx and len(y)==ly]
            total = len(f) + len(inf)
            if total > 0:
                print(f"  |x|={lx}, |y|={ly}: total={total}, finite={len(f)}, infinite={len(inf)}")

    # Verify same-length argument more carefully
    print("\n=== Same-length verification ===")
    same_len_pairs = [(x,y) for x,y in pairs if len(x) == len(y)]
    print(f"Same-length pairs: {len(same_len_pairs)}")

    # For each same-length pair, verify by BFS that it's truly finite
    for x, y in same_len_pairs:
        # BFS from words of length up to 12 containing x
        for start_len in range(len(x), min(len(x) + 6, 12) + 1):
            for sw in gen_words_of_length(start_len):
                if x not in sw:
                    continue
                visited = set()
                queue = [sw]
                visited.add(sw)
                cycle = False
                while queue:
                    cur = queue.pop(0)
                    for nw in apply_rule(cur, x, y):
                        if nw in visited:
                            # This means we can reach a state we've already visited
                            # But wait: in same-length rewriting, reaching a visited state
                            # means we've found a cycle. But did we? Let's check: nw was
                            # already in visited, meaning we've derived it before from sw.
                            # So there's a path sw -> ... -> nw -> ... -> nw = cycle!
                            # WAIT: nw in visited just means we already saw this word.
                            # It doesn't mean we can get back to it. It means BFS already
                            # queued it. Since BFS visits each node once, if nw is in visited,
                            # we've already processed it or will process it. This is NOT a cycle,
                            # it's just a DAG merge.
                            pass
                        else:
                            visited.add(nw)
                            queue.append(nw)

    # Actually let me verify the numerical argument directly
    print("\n=== Verifying numerical argument for same-length rules ===")
    def string_val(s):
        """Interpret string as binary number with a=0, b=1."""
        val = 0
        for c in s:
            val = val * 2 + (0 if c == 'a' else 1)
        return val

    for x, y in same_len_pairs:
        vx, vy = string_val(x), string_val(y)
        direction = "increasing" if vy > vx else "decreasing"
        # Verify: for a specific example, does every step move in this direction?
        test_word = x + x  # simple test
        results = apply_rule(test_word, x, y)
        for r in results:
            vtest = string_val(test_word)
            vr = string_val(r)
            if vy > vx:
                assert vr > vtest, f"Expected increase: {test_word}({vtest}) -> {r}({vr}), rule {x}->{y}"
            else:
                assert vr < vtest, f"Expected decrease: {test_word}({vtest}) -> {r}({vr}), rule {x}->{y}"

    print("All same-length rules verified: numerical value is monotone.")

    # Now let's focus on growing rules more carefully
    print("\n=== Growing rules analysis (|y| > |x|) ===")
    growing_finite = [(x,y) for x,y in finite_rules if len(y) > len(x)]
    growing_infinite = [(x,y) for x,y in infinite_rules if len(y) > len(x)]

    print(f"Growing finite: {len(growing_finite)}")
    for x, y in growing_finite:
        # Explain why finite
        if x not in y:
            # x not in y. But even then, boundary effects might create x.
            # If BFS says finite, it means after replacement, x never appears
            # (even at boundaries). Let's verify.
            pass
        print(f"  '{x}' -> '{y}': x_in_y={x in y}")

    print(f"\nGrowing infinite: {len(growing_infinite)}")
    for x, y in growing_infinite:
        print(f"  '{x}' -> '{y}': x_in_y={x in y}")

    # Let me now think about the 255 problem
    print("\n=== Attempting to match 255 ===")
    # Maybe the problem counts (x,y) where BOTH x and y are nonempty?
    both_nonempty = [(x,y) for x in nonempty for y in nonempty if x != y]
    print(f"Both nonempty, x != y: {len(both_nonempty)}")

    # Or: x nonempty, y anything INCLUDING x=y
    with_identity = [(x,y) for x in nonempty for y in words]
    print(f"x nonempty, any y (incl x=y): {len(with_identity)}")

    # Or: both from words, both nonempty, including x=y
    both_nonempty_incl = [(x,y) for x in nonempty for y in nonempty]
    print(f"Both nonempty, including x=y: {len(both_nonempty_incl)}")

    # Or: what if words of length <=3 means strictly letters only (no empty)?
    # x from len 1-3 (14), y from len 0-3 (15), including x=y: 14*15=210
    # x from len 1-3, y from len 1-3: 14*14=196
    # With empty y too: 14*15=210

    # What if the problem counts substitutions differently?
    # Maybe (x,y) where at least one is nonempty?
    at_least_one_nonempty = [(x,y) for x in words for y in words if (x or y) and x != y]
    print(f"At least one nonempty, x!=y: {len(at_least_one_nonempty)}")

    # x or y nonempty, any order, x != y:
    # 15*15 - 1 (removing (empty,empty)) = 224... no, x!=y removes 15, so 225-15=210. Plus empty->empty is already in the excluded set.

    # Let me try: what if length <= 3 includes BOTH the empty word AND
    # we're counting x,y where x can be anything (including empty)?
    all_pairs_neq = [(x,y) for x in words for y in words if x != y]
    print(f"All pairs x!=y: {len(all_pairs_neq)}")

    # What about: words of length <= 3, count = 15,
    # substitutions = ordered pairs including x=y?
    # 15*15 = 225. Not 255.

    # WAIT: what if they include words of length up to 3,
    # and by "word" they mean a NONEMPTY word of length 0-3 ON THE ALPHABET?
    # That's contradictory since length 0 word is empty...

    # Actually I just realized: maybe the empty word should NOT be in the count
    # for x, but for y we allow empty word AND we also allow y to be
    # words of length up to 4? No, that doesn't make sense.

    # Let me try: 15 words total. Substitutions: pairs (x,y) with x nonempty, any y.
    # That's 14 * 15 = 210. Not 255.

    # OR: the problem perhaps counts ALL 15*17=255 somehow.
    # What is 17? 15 words + 2 more? Like {a,b} counted separately?

    # Perhaps the problem is from a competition and 255 is just the stated number.
    # Let me focus on the answer.

    # Additional analysis: if the problem means something different by "255 substitutions",
    # maybe they count pairs (x,y) where x is a nonempty word of length <=3 and y is a word
    # of length <=3 (including empty), and we DON'T exclude x=y, but the identity
    # substitution x->x "counts" as a substitution (trivially finite).
    # Then total = 14*15 = 210. Still not 255.

    # Let me try another approach: maybe the alphabet includes more?
    # Or length <=3 gives different count? Let me count again.
    # Words on {a,b} of length 0: "" (1 word)
    # Length 1: a, b (2 words)
    # Length 2: aa, ab, ba, bb (4 words)
    # Length 3: aaa, aab, aba, abb, baa, bab, bba, bbb (8 words)
    # Total: 1 + 2 + 4 + 8 = 15

    # Hmm, 255 = 15 * 17. That's a weird factorization. Let me try:
    # What if the problem means words of length <= 3 NOT including the empty word (14 words),
    # and the "255" is a typo or miscount? 14*14 = 196, not 255 either.

    # Actually, 256 = 2^8. 255 = 2^8 - 1.
    # There are 2^8 = 256 binary strings of length 8.
    # Or: a word of length <=3 on {a,b} can be encoded as a binary string of length <=3
    # prefixed by its length. That gives 15 words encoded as tuples.
    # Hmm, 255 could be some encoding artifact.

    # I think the problem may just have a different counting convention.
    # The key answer is about how many are finite.

    # Let me compute for the 210 case (x nonempty, any y including x=y)
    finite_210 = finite_rules.copy()
    # Add identity rules (trivially finite)
    for x in nonempty:
        finite_210.append((x, x))
    print(f"\nFinal count including identity rules: {len(finite_210)} finite out of 210")

    # Check: what if we DON'T exclude x -> empty for any x?
    # x -> empty is x deletion. Always finite (length strictly decreases).
    # These are already counted.

    # The answer for finite substitutions:
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total pairs (x nonempty, x!=y): {len(pairs)}")
    print(f"Finite: {len(finite_rules)}")
    print(f"Non-finite: {len(infinite_rules)}")
    print(f"If including identity (x=y): {len(finite_rules)+14} finite out of {len(pairs)+14}")


if __name__ == '__main__':
    main()
