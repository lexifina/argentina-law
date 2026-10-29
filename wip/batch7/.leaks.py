import sys, re
sys.path.insert(0, 'batch7')
import parse_batch7 as B, parse as P
for s in B.SETS[1:]:
    s['skip'] = True
B.install()
act = P.act_order()[-1]
r = B.replay(act)
seen = set()
for i, v in enumerate(r['versions']):
    for k, u in v['state'].items():
        for l in u['body']:
            m = re.search(r'\((?:[^()]|\([^()]*\))*?(?:incorporad|sustituid|derogad|modificad|vetad|observad)[oa]s?\s+por\b.*$', l)
            if (m or 'B.O.' in l or 'Infoleg' in l) and (k, l) not in seen:
                seen.add((k, l))
                print(i, k, '|', (m.group(0) if m else l)[:220])
