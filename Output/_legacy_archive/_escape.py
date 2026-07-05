import sys; sys.path.insert(0,'ProgramFiles')
import twographs as tg, properties as P, iso
db=[l.strip() for l in open('ProcessFiles/known37/all_canonical.g6') if l.strip()]
db_set=set(db)
seen=set(); escapes=set(); bad_ext=0; nonsrg=0
for g6 in db:
    if g6 in seen: continue
    G=iso.graph6_to_matrix(g6)
    ext=tg.extend_isolated(G)
    reg,ab=tg.is_regular_two_graph(ext)
    if not reg: bad_ext+=1
    fam=set(tg.switching_family_srg37(G))
    seen|= (fam & db_set); seen.add(g6)
    esc=fam-db_set
    escapes|=esc
print('classes seen cover',len(seen),'bad_ext',bad_ext,'raw_escapes',len(escapes),flush=True)
esc_canon=set(iso.canonical_forms(sorted(escapes))) if escapes else set()
still=esc_canon-db_set
print('escapes canon',len(esc_canon),'still outside db',len(still),flush=True)
for g in list(still)[:5]:
    M=iso.graph6_to_matrix(g); r=P.verify_srg(M,37,18,8,9)
    print('escape valid SRG?',r['ok'],'omega',P.max_clique_size(M),'2rank',P.rank_mod_p(M,2),flush=True)
