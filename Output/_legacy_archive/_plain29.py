import os,sys,time
sys.path.insert(0,'ProgramFiles')
# daemonize
if os.fork()>0: os._exit(0)
os.setsid()
if os.fork()>0: os._exit(0)
fd=os.open('Output/_plain29.out',os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o644)
os.dup2(fd,1); os.dup2(fd,2)
import sat_backend as sb, iso
from srg_encoder import CNFBuilder, add_srg_constraints, SRGSpec
b=CNFBuilder(29); meta=add_srg_constraints(b,SRGSpec(29,14,6,7)); b.to_dimacs('Output/c29.cnf')
t=time.time()
r=sb.run_smsg('Output/c29.cnf',29,initial_partition=meta['initial_partition'])
uniq=len(set(iso.canonical_forms([iso.matrix_to_graph6(m) for m in r['matrices']]))) if r['matrices'] else 0
print(f'PLAIN29 n_graphs={r["n_graphs"]} raw={len(r["matrices"])} uniq={uniq} completed={r["completed"]} t={time.time()-t:.1f}',flush=True)
