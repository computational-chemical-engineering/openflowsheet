"""Compare two answer records of ``recplug.py`` (spec §19.7, A46): ``python cmp.py OLD NEW``.

A request key is ``tag|component|first argument``. A key whose answers are identical counts as
identical. A key the old record answered with ``None`` or a refusal may change (a former refusal
now answered). Any other change is an ANSWER CHANGED and makes the exit status 1.
"""

import sys
from collections import defaultdict


def load(path):
    d = defaultdict(set)
    with open(path) as handle:
        for line in handle:
            tag, fluid, req, res = line.rstrip("\n").split("|", 3)
            d[(tag, fluid, req)].add(res)
    return d


old, new = load(sys.argv[1]), load(sys.argv[2])
same = changed_from_refusal = bad = only_old = 0
bad_examples = []
for key, olds in old.items():
    if key not in new:
        only_old += 1
        continue
    news = new[key]
    if olds == news:
        same += 1
        continue
    o = next(iter(olds))
    if len(olds) == 1 and (o == "None" or ("status=" in o and "status='ok'" not in o)):
        changed_from_refusal += 1
    else:
        bad += 1
        if len(bad_examples) < 5:
            bad_examples.append((key, olds, news))
only_new = sum(1 for k in new if k not in old)
print(
    f"keys old {len(old)} new {len(new)}: identical {same}, refusal/None->changed "
    f"{changed_from_refusal}, ANSWER CHANGED {bad}, only-old {only_old}, only-new {only_new}"
)
for ex in bad_examples:
    print("BAD", str(ex)[:600])
sys.exit(1 if bad else 0)
