import sys, difflib
sys.path.insert(0, 'batch7')
import parse_batch7 as B, parse as P
B.install()
act = P.act_order()[-1]
L, _, _ = B.act_lines(-B.NID, "norma.htm", act["start"], act["end"])
T, _, _ = B.act_lines(B.NID, "texact.htm", act["start"], act["end"])
b = P.split_units(L, width=4); t = P.split_units(T, width=4)
for k in sys.argv[1:]:
    print("=====", k, "notes:", t.get(k, {}).get("notes"))
    for l in difflib.unified_diff(P.body_of(b.get(k)), P.body_of(t.get(k)), lineterm="", n=0):
        print(l[:400])
