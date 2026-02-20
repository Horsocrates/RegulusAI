from itertools import product

def gen_words(max_len):
    words = ['']
    for length in range(1, max_len + 1):
        for combo in product('ab', repeat=length):
            words.append(''.join(combo))
    return words

def find_occ(word, pat):
    if pat == '':
        return list(range(len(word) + 1))
    pos_list = []
    start = 0
    while True:
        p = word.find(pat, start)
        if p == -1:
            break
        pos_list.append(p)
        start = p + 1
    return pos_list

def is_finite(x, y, max_wlen=20, max_steps=300):
    if x == y:
        return True
    if x == '':
        return y == ''
    if len(y) < len(x):
        return True

    for start_len in range(len(x), min(len(x) + 6, max_wlen + 1)):
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
                    for p in find_occ(w, x):
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
                frontier = nxt
                steps += 1
            if steps >= max_steps:
                return False
    return True

words = gen_words(3)
print(f"Total words: {len(words)}")
print(f"Total pairs: {len(words)**2}")

finite_count = 0
for x in words:
    for y in words:
        if is_finite(x, y):
            finite_count += 1

print(f"Finite: {finite_count}")
print(f"Infinite: {len(words)**2 - finite_count}")
