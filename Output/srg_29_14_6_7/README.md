# SRG(29, 14, 6, 7) — status

The known non-isomorphic count for these parameters is **41** (Brouwer's
tables, conference graph on 29 vertices). This directory now holds a
**complete** enumeration.

## What is stored here

* `graphs/graphs.g6`, `graphs/graphs.jsonl` — **41** canonical graphs (from
  the authoritative `runs/full_smsg` enumeration).
* `runs/full_smsg/` — complete plain-`smsg` run (`search_complete: true`,
  9397 s, 41 graphs). Includes `summary.json`, graph artifacts, and
  `formula.cnf` (when run with `--keep-cnf`).
* `campaigns/rehearsal29/` — completed cube-and-conquer campaign
  (`search_complete: true`) with **18** graphs. Partial subset kept for
  provenance / decomposition replay.
* `campaigns/rehearsal29b/` — abandoned campaign (`search_complete: false`,
  6 cubes timed out, 0 graphs recovered). Kept for provenance only.

## Re-running full enumeration

Every `enumerate.py` run with the same tag refreshes the whole SRG directory
layout for that run:

```bash
python -u Automators/enumerate.py --v 29 --k 14 --lam 6 --mu 7 \
    --backend smsg --tag full_smsg --keep-cnf --out Output \
    --live-progress --progress-interval 10
```

That updates:

* `runs/full_smsg/graphs.{g6,jsonl}`
* `runs/full_smsg/summary.json`
* `runs/full_smsg/formula.cnf` (with `--keep-cnf`)
* `graphs/graphs.{g6,jsonl}` (catalog replaced on complete unconstrained runs)
* `summary.json` (top-level SRG index)
