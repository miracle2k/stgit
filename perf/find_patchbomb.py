# Feed this with git rev-list HEAD --parents

import sys

parents = {}
for line in sys.stdin.readlines():
    commits = line.split()
    parents[commits[0]] = commits[1:]

sequence_num = {}
stack = []
for commit in parents.keys():
    stack.append(commit)
    while stack:
        c = stack.pop()
        if c in sequence_num:
            continue
        ps = parents[c]
        if len(ps) == 1:
            p = ps[0]
            if p in sequence_num:
                sequence_num[c] = 1 + sequence_num[p]
            else:
                stack.append(c)
                stack.append(p)
        else:
            sequence_num[c] = 0

(num, commit) = max((num, commit) for (commit, num)
                    in sequence_num.iteritems())
print '%s is a sequence of %d patches' % (commit, num)
