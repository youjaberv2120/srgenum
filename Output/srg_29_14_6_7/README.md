# SRG(29, 14, 6, 7) — status

The known non-isomorphic count for these parameters is **41** (Brouwer's
tables, conference graph on 29 vertices).

## What is stored here right now

* `graphs/graphs.g6`, `graphs/graphs.jsonl` — 18 canonical graphs recovered
  from the legacy cube-and-conquer campaign `rehearsal29` (see
  `campaigns/rehearsal29/`). This is a *partial* set: the aggressive
  cube-cutoff used for that rehearsal missed graphs living in cubes that were
  either merged coarsely or where the shard was dropped before the merge.

* `campaigns/rehearsal29/` — completed campaign (`search_complete: true`)
  with `distinct_graphs: 18`. Useful for reproducing that specific decomposition.
* `campaigns/rehearsal29b/` — abandoned campaign (`search_complete: false`,
  6 cubes timed out, 0 graphs recovered). Kept for provenance only.
* `runs/full_smsg/` — placeholder for the full plain-`smsg` enumeration.
  Populated once the background job (see below) completes.

## Full enumeration

An in-process plain `smsg` enumeration takes roughly **~2.5 hours**
(single-threaded; a previous ad-hoc run finished in 8852 s and reported all
41 graphs, but the run did not persist them). A fresh run was kicked off with:

```bash
nohup .venv/bin/python Automators/enumerate.py \
    --v 29 --k 14 --lam 6 --mu 7 --backend smsg \
    --tag full_smsg --keep-cnf --out output \
    > Output/_srg29_full.log 2>&1 &
```

When it finishes, it will write:

* `runs/full_smsg/graphs.g6` + `graphs.jsonl` — all 41 graphs
* `runs/full_smsg/summary.json` — full run metadata
* An updated `../graphs/graphs.g6` + `graphs.jsonl` catalog (auto-merged via
  `output_layout.upsert_srg_catalog`)
* An updated `../summary.json` (auto-merged)

After completion, rerun `scripts/mirror_to_srgenum.sh` to sync the new files
into the sibling `srgenum/` clone and push.
