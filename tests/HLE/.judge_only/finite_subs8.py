"""
Final verification:
1. Are all same-length rules really finite? (especially |x|=|y|=3)
2. Are the 18 growing-finite rules really finite?
3. Are the 4 borderline growing-infinite rules really infinite?
4. Re-examine: could there be growing rules with |x|=3, |y|>3... oh wait, |y|<=3 too.
   So |x|=3 implies |y| can only be 0,1,2,3. |y|>|x|=3 is impossible.
   So growing rules with |x|=3 don't exist. Correct.

Focus: the "LIKELY INFINITE" cases from the previous run.
These are the ones that hit the state limit but didn't confirm by exceeding word length.
Let me check them with even bigger limits or analytically.
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

def check_specific(x, y, start, max_len=300, max_states=500000):
    """Check a specific starting word with very large limits."""
    visited = set()
    queue = deque([start])
    visited.add(start)
    max_word = len(start)

    while queue:
        current = queue.popleft()
        nexts = apply_rule_all(current, x, y)
        for nw in nexts:
            if len(nw) > max_len:
                return f"INFINITE (grew beyond {max_len})", max_word, len(visited)
            if nw not in visited:
                visited.add(nw)
                queue.append(nw)
                if len(nw) > max_word:
                    max_word = len(nw)
        if len(visited) > max_states:
            return f"UNKNOWN (>{max_states} states, max_word={max_word})", max_word, len(visited)

    return f"FINITE (max_word={max_word})", max_word, len(visited)


def main():
    # Check the "LIKELY INFINITE" cases from previous runs
    print("=== Checking borderline cases with larger limits ===\n")

    borderline = [
        # ab -> baa: from aabbbbbbb was "UNKNOWN"
        ('ab', 'baa', 'aabbbbbbb'),
        # ab -> bba: from aaaaaaaab was "UNKNOWN"
        ('ab', 'bba', 'aaaaaaaab'),
        ('ab', 'bba', 'aaaaaaabb'),
        ('ab', 'bba', 'aaaaaabab'),
        ('ab', 'bba', 'aaaaaabbb'),
        # ba -> aab: nothing borderline but let me check
        # ba -> abb: from baaaaaaaa was "UNKNOWN"
        ('ba', 'abb', 'baaaaaaaa'),
    ]

    for x, y, start in borderline:
        result, max_w, states = check_specific(x, y, start, max_len=300, max_states=500000)
        print(f"  '{x}' -> '{y}', start='{start}': {result} ({states} states)")

    # Even if the BFS from these specific words doesn't conclusively prove infinity,
    # we ALREADY proved each of these 4 rules infinite from other starting words!
    # ab -> baa: INFINITE from 'aababbbbb' (confirmed growth >150)
    # ab -> bba: INFINITE from 'aaaaabaab' (confirmed growth >150)
    # ba -> aab: INFINITE from 'bbbbabbba' (confirmed growth >150)
    # ba -> abb: INFINITE from 'baaabaaaa' (confirmed growth >150)
    # So all 4 are definitely infinite.

    print("\n=== Double-checking the 18 finite growing rules ===\n")

    finite_growing = [
        ('a', 'bb'), ('a', 'bbb'),
        ('b', 'aa'), ('b', 'aaa'),
        ('aa', 'aba'), ('aa', 'abb'), ('aa', 'bab'), ('aa', 'bba'), ('aa', 'bbb'),
        ('ab', 'aaa'), ('ab', 'bbb'),
        ('ba', 'aaa'), ('ba', 'bbb'),
        ('bb', 'aaa'), ('bb', 'aab'), ('bb', 'aba'), ('bb', 'baa'), ('bb', 'bab'),
    ]

    for x, y in finite_growing:
        # Analytical argument for finiteness:
        # Key: does y contain any character from x?
        # More precisely: does x appear in y? (NO for all, already checked)
        # Can boundary effects create new x?

        # For a -> bb (or a -> bbb):
        # y has no 'a'. Each step removes one 'a' and adds 'b's.
        # #a decreases by 1 each step. Finite. ✓

        # For b -> aa (or b -> aaa):
        # y has no 'b'. Each step removes one 'b'. Finite. ✓

        # For aa -> aba: y doesn't contain 'aa'.
        # But 'a' + 'aba' = 'aaba' contains 'aa'!
        # However: each step replaces 'aa' by 'aba', which preserves #a and increases #b.
        # More importantly: the number of 'aa' (overlapping) pairs in the string.
        # In 'aa' there's 1 pair. In 'aba' there are 0 pairs.
        # But boundary can create a pair: if context is '...a aa ...', replacing gives '...a aba ...' = '...aaba...' which has 1 'aa'.
        # So we go from 1 pair (the one we replaced) to at most 1 pair (at boundary).
        # Net: #aa_pairs doesn't increase. But can it cycle?
        # #b increases by 1 each step (aa has 0 b's, aba has 1 b).
        # Since length grows but #a is fixed, eventually all adjacent pairs are separated by b's.
        # So finite. ✓

        # For aa -> bbb: y has no 'a'. Each step replaces 2 a's by 0 a's (adds 3 b's).
        # #a decreases by 2 each step. Finite. ✓

        # For ab -> aaa: y has no 'b'. Each step removes one 'b'. Finite. ✓
        # For ab -> bbb: y has no 'a'. Each step removes one 'a'. Finite. ✓

        # For ba -> aaa: y has no 'b'. Each step removes one 'b'. Finite. ✓
        # For ba -> bbb: y has no 'a'. Each step removes one 'a'. Finite. ✓

        # For bb -> aaa: y has no 'b'. Each step removes 2 b's. Finite. ✓
        # For bb -> aba: y has no 'bb'. y='aba'.
        # 'aba' + 'b' = 'abab' contains 'bb'? No! 'bb' not in 'abab'.
        # 'b' + 'aba' = 'baba'. 'bb' not in 'baba'.
        # So no boundary effects create 'bb'. Finite. ✓

        # For bb -> bab: y = 'bab'. 'bb' not in 'bab'.
        # Boundary: 'b' + 'bab' = 'bbab' contains 'bb'!
        # And 'bab' + 'b' = 'babb'. No 'bb' here.
        # So left boundary can create 'bb'.
        # But: #b in 'bb' = 2, #b in 'bab' = 2. #b preserved.
        # #a increases by 1. String grows.
        # But: each step either creates a new 'bb' at the left boundary or not.
        # The 'bb' that was replaced is gone, replaced by 'bab'. If a new 'bb' forms
        # at the left boundary (from context 'b' + 'bab' = 'bbab'), that's one new 'bb'.
        # So #bb stays the same or decreases. But length grows.
        # Since #b is fixed and length grows, the b's get more spread out.
        # Eventually no two b's are adjacent. Finite. ✓

        # Similar analysis for other bb->... rules.

        pass

    # Let me verify with large BFS one more time
    for x, y in finite_growing:
        max_start = min(len(x) + 12, 14)
        found_issue = False
        for sl in range(len(x), max_start + 1):
            if found_issue:
                break
            for sw in gen_words_of_length(sl):
                if x not in sw:
                    continue
                result, mw, states = check_specific(x, y, sw, max_len=300, max_states=300000)
                if 'INFINITE' in result or 'UNKNOWN' in result:
                    print(f"  PROBLEM: '{x}' -> '{y}', start='{sw}' (len={sl}): {result}")
                    found_issue = True
                    break
        if not found_issue:
            print(f"  '{x}' -> '{y}': CONFIRMED FINITE (all starts up to len {max_start})")


if __name__ == '__main__':
    main()
