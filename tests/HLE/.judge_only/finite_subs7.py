"""
Figure out the 255 counting and determine the final answer.

Possible interpretation: The problem counts substitutions as (x, y) where:
- Both x and y are words on {a,b} of length <= 3 (including empty)
- (x, y) with x != y
- Total: 15*15 - 15 = 210. STILL NOT 255.

OR: maybe x can equal y? Then 15*15=225. Not 255.

OR: maybe they count words of length <= 3 differently? Like including
the "undefined" or some special word?

Actually wait: let me re-read the problem statement more carefully.
"Consider words on the two letters alphabet {a,b}."
"For a substitution x->y (where x and y are two words on this alphabet)"
"Consider all possible couples (x,y) of words of length <= 3 (we allow for the empty word)."
"Out of the 255 associated substitutions, how many are finite?"

Hmm, 255 = 15*17. What if they count words of length <= 3 as 17?
On alphabet of size 2: length 0: 1, length 1: 2, length 2: 4, length 3: 8. Total=15.
On alphabet of size 3: length 0: 1, length 1: 3, length 2: 9, length 3: 27. Total=40.

What if the "two letters alphabet" means the WORDS use exactly two letters
(must contain both a and b)? No, that doesn't make sense.

OR: what if by "couples" they mean ORDERED pairs where x != y?
15*14 = 210. No.

Wait, could it be 15*15 - 15 + ... = 255?
225 + 30 = 255. Where does 30 come from?

OR: 15 * (15+2) = 15*17 = 255. What's the +2?
Maybe y can also be words of length 4? No, that seems unlikely.

Actually... let me consider: maybe "length <= 3" for x means length 1, 2, or 3
(i.e., x must be nonempty), and "length <= 3" for y means length 0, 1, 2, or 3.
Then x: 14 words, y: 15 words. But the problem says "couples (x,y) of words
of length <= 3", implying both from the same set.

Hmm, wait. What if the problem counts each word pair TWICE because the
substitution x->y is different from y->x? That's already what ordered pairs do.

Let me try: 255 = 15 choose 2 * ... No, 15 choose 2 = 105.
2 * 105 = 210. Plus 15 identity = 225. Plus 30??

I'm going to try a completely different interpretation:
What if "words of length <= 3" means words of length EXACTLY 3 or less,
but they count the number of DISTINCT substitutions (as functions on all words)?
Two different pairs (x1,y1) and (x2,y2) might define the same substitution.
But that seems unlikely with these small words.

Or maybe: the problem means x is nonempty and both x,y have length <= 3.
Excluding x=y, that's 14*15-14 = 196. Including x=y: 14*15 = 210.
Neither is 255.

OK I give up on matching 255 exactly. Let me just accept that there might be
a slightly different convention and report:
- Out of 196 non-identity substitutions (x nonempty, x != y): 158 finite
- Out of 210 substitutions (x nonempty, any y): 172 finite
- The percentage: 158/196 ≈ 80.6% or 172/210 ≈ 81.9%

If the problem has 255 substitutions and the same ratio: 255 * 0.806 ≈ 206
or 255 * 0.819 ≈ 209.

But that's just guessing. Let me check: if we scale the infinite count.
38 infinite out of 196 = 19.4%. 255 * 0.194 = 49.5.
255 - 50 = 205? Or 255 - 49 = 206?

Hmm, that doesn't feel right either. Let me think about this from scratch.

Wait... maybe I should check: what about x = empty, y = empty?
That's x=y, identity, trivially finite.

What about x = empty, y = 'a'?
Inserting 'a' anywhere. Starting from 'b':
b -> bа or ab. Both contain b, so we can insert again.
b -> ab -> aab or aba or ab...
This grows without bound. INFINITE.

What about x = empty, y = nonempty word?
We can insert y BETWEEN any two adjacent characters, or at the start/end.
Starting from any nonempty word, we can keep inserting. INFINITE.

So empty -> nonempty is always infinite (14 such rules).
Empty -> empty is identity (finite).

If we include these:
Total = 15*15 = 225 pairs. Minus 15 identities = 210.
But 210 != 255.

OR: total = 15*15 - 15 = 210 non-identity substitutions.
Finite non-identity: 158 (from nonempty x) + 0 (from empty x, since all are infinite) = 158.

Hmm wait, with empty x:
empty -> nonempty: 14 rules, all infinite.
So total infinite = 38 + 14 = 52.
Total finite = 158.
Total = 210. Finite/total = 158/210.

Including identity: 158 + 15 = 173. Wait, earlier I said 172. Let me recheck.

158 (non-identity finite with x nonempty) + 14 (identity with x nonempty)
= 172 (total finite with x nonempty)
Plus 1 (identity with x = empty, i.e., empty -> empty) = 173.

Total with everything: 15*15 = 225.
Finite: 173.
Non-trivially finite (exclude identity): 158.
Infinite: 225 - 173 = 52 (= 38 from x nonempty + 14 from x empty).

None of this gives 255 total.

FINAL ATTEMPT: Maybe the problem counts "words of length <= 3" as follows:
the empty word PLUS words of length 1,2,3. But "length <= 3" might mean
the number of letters is at most 3, and on a 2-letter alphabet:
- 0 letters: 1 word (empty)
- 1 letter: 2 words
- 2 letters: 4 words
- 3 letters: 8 words
Total: 15.

But what if they DON'T include the empty word in the word count,
and "we allow for the empty word" is a separate addition?
Then words: 14 nonempty + 1 empty = 15. Still 15.

255 = 256 - 1 = 2^8 - 1.
Note: a word of length <= 3 on {a,b} can be encoded as a bitstring of length <=3.
The number of such bitstrings: 1 + 2 + 4 + 8 = 15.
But 2^8 = 256 encodes ALL bitstrings of length 8.

OH WAIT. Maybe the problem encodes each word as a binary string of length UP TO 3,
and there are 2^1 + 2^2 + 2^3 = 2 + 4 + 8 = 14 nonempty words.
"We allow the empty word" means + 1 = 15 for y.
And x must be nonempty: 14.
Substitutions: all (x,y) where x is nonempty and y is any word, x != y.
= 14 * 15 - 14 = 196. STILL NOT 255.

I think there might be an error in the problem statement (255 vs 225 or something),
or a convention I'm not seeing.

The answer given my analysis:
"""

# Just double-check the numbers
print("Words of length 0:", 1)
print("Words of length 1:", 2)
print("Words of length 2:", 4)
print("Words of length 3:", 8)
print("Total:", 15)
print()
print("15^2 =", 15**2)
print("15^2 - 15 =", 15**2 - 15)
print("14 * 15 =", 14 * 15)
print("14 * 15 - 14 =", 14 * 15 - 14)
print()

# The answer
print("ANSWER:")
print("Finite (x nonempty, x!=y): 158 out of 196")
print("Finite (x nonempty, any y): 172 out of 210")
print("Finite (any x, x!=y): 158 out of 210")
print("Finite (any x, any y): 173 out of 225")

# Now let me check: 255 could be 225 + 30. Where 30 = number of substitutions
# that also include x -> y where |x| <= 3 and |y| = 4 perhaps?
# If we add y of length 4 (16 more words), then y has 15+16=31 choices.
# But x still has 14 choices (nonempty, length <=3).
# Total: 14 * 31 - 14 = 14*30 = 420. Too many.
# Or: 15 * (15+16) - 15 = 15*31-15 = 450. Way too many.

# Alternatively: 255 = 2^8 - 1. What if the problem counts substitutions differently?
# Like: for each possible rule (x,y), multiple "substitutions" exist if x appears
# multiple times in a word? No, the substitution IS the rule.

# OR: The 255 might be a typo for 225 (15*15).
# In that case: 225 total (all ordered pairs of words of length <=3).
# Finite: 173 (including 15 identities).
# Non-trivially finite: 158.

# If the problem means 225 and asks for finite ones including identity:
print("\nIf 225 total (all ordered pairs, 15*15):")
print("Finite: 173 (158 non-identity + 15 identity)")

# If the problem means 225 and identity is not a "substitution":
print("\nIf 210 total (ordered pairs with x!=y):")
print("Finite: 158")

# WAIT - one more idea. What if the problem doesn't exclude x = ε?
# And ε -> ε is a valid substitution (identity, finite)?
# And ε -> y for nonempty y: is this infinite? Let me reconsider.
#
# The problem says "we naturally extend it to any word containing the subword x
# by wxw' -> wyw'." For x = ε, EVERY word w contains ε as a subword
# (at every position). So ε -> y inserts y at every position.
# But we apply ONE occurrence at a time: pick one position between characters
# and insert y there.
#
# From "a": ε -> 'b' gives "ba" or "ab". From "ab": insert 'b' at 3 positions:
# "bab", "abb", "abb". Wait, "abb" from two positions. Hmm.
# Actually from 'ab': ε occurs at positions 0, 1, 2 (before a, between a and b, after b).
# Insert 'b': 'bab', 'abb', 'abb'. So two distinct results: 'bab', 'abb'.
# From 'bab': 'bbab', 'babb', 'babb', 'babb'. Distinct: 'bbab', 'babb'.
# This keeps going forever. So ε -> nonempty is INFINITE.
#
# So: ε -> nonempty: 14 rules, all infinite.
# ε -> ε: 1 rule, finite (identity).
# Total finite unchanged: 158 (from nonempty x, x != y).
# Plus 15 identity rules (14 x=y for nonempty + 1 for ε): 173.

# The answer I'm most confident in:
print("\n" + "="*60)
print("MOST CONFIDENT ANSWER")
print("="*60)
print()
print("Rules x -> y with x, y words on {a,b}, |x|, |y| <= 3:")
print(f"  Total non-identity substitutions (x nonempty, x!=y): 196")
print(f"  Finite non-identity substitutions: 158")
print(f"  Infinite non-identity substitutions: 38")
print()
print("If the problem means 255 total and asks how many are finite:")
print("  We cannot match the 255 count exactly.")
print("  But the number of finite rules is 158 (or 172 including identity).")
print()
print("Given the problem likely has 225 = 15^2 substitutions total:")
print("  Finite: 173")
print("  Infinite: 52")
