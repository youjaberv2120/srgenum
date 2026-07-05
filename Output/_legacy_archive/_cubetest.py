import sys; sys.path.insert(0,'ProgramFiles')
from srg_encoder import CNFBuilder, add_srg_constraints, SRGSpec
import sat_backend as sb, iso, time
for (v,k,l,m,exp,co) in [(16,6,2,2,2,6),(25,12,5,6,15,6)]:
    t0=time.time()
    b=CNFBuilder(v); meta=add_srg_constraints(b,SRGSpec(v,k,l,m)); cnf=f'Output/cc{v}.cnf'; b.to_dimacs(cnf)
    cubes=sb.generate_cubes(cnf,v,co,initial_partition=meta['initial_partition'])
    cf=f'Output/cubes{v}.txt'; open(cf,'w').write('\n'.join(cubes)+'\n')
    allm=[]; ncomplete=0
    for i in range(1,len(cubes)+1):
        r=sb.run_smsg(cnf,v,initial_partition=meta['initial_partition'],cube_file=cf,cube_line=i,timeout=120)
        allm+=r['matrices']; ncomplete+= 1 if r['completed'] else 0
    uniq=len(set(iso.canonical_forms([iso.matrix_to_graph6(x) for x in allm])))
    print(f'SRG({v},{k},{l},{m}): cubes={len(cubes)} completed={ncomplete} raw={len(allm)} uniq={uniq} expected={exp} {"OK" if uniq==exp else "FAIL"} t={time.time()-t0:.1f}',flush=True)
