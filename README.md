# Multi-Stage Enumeration of SRG(37, 18, 8, 9)

An ALL-SAT pipeline for the strongly regular graphs with parameters
(37, 18, 8, 9) - the **first open case** in the classification of strongly
regular graphs (every SRG on <= 36 vertices is fully enumerated; at least
**6766** SRG(37,18,8,9) are known, and the exact total is unknown).

The pipeline encodes the SRG property in CNF, enumerates models isomorph-free,
and validates every output graph, using:

* **SAT Modulo Symmetries (SMS / `smsg`)** - isomorph-free enumeration with
  *dynamic* symmetry breaking, built on CaDiCaL. Preferred backend.
* **PySAT + CaDiCaL** - in-process projected ALL-SAT (blocking clauses on the
  edge variables) as an always-available fallback.
* **nauty** (`labelg` / `shortg`) - canonical labelling / isomorph rejection.

SRG(37,18,8,9) is a **conference graph** (`k=(v-1)/2`, `lambda=(v-5)/4`,
`mu=(v-1)/4`), with irrational eigenvalues `(18, (-1+/-sqrt37)/2)` each of
multiplicity `(1, 18, 18)`. The concrete Paley graph `P(37)` is one such graph
(the unique one with `|Aut| = 666`).

## Layout

```
ProgramFiles/
  srg_encoder.py     SMS-compatible CNF encoder (edge vars in combinations
                     order), degree/lambda/mu via Sinz sequential counters,
                     conference identity, clique/coclique bounds. Core module.
  sat_backend.py     PySAT/CaDiCaL projected ALL-SAT + smsg streaming backend.
  iso.py             graph6 I/O + nauty canonicalisation / dedup.
  properties.py      P1-P12 invariants (SRG check, clique adjacency bound,
                     p-rank, spectrum, complement, neighbourhood regularity).
  neighborhood_cnf.py  legacy entry point, now a shim over srg_encoder.
  twographs.py       Seidel switching + two-graph descendants (the (37) route).
  output_layout.py   shared output paths + graph artifact writers.
Automators/
  enumerate.py       main pipeline: encode -> solve -> dedup -> validate -> save.
  stage.py           multi-stage max-clique anchor decomposition (omega in {3,4,5}).
  validate.py        correctness harness: known-count matrix (both backends) +
                     Paley(37) recognition + negative control + ground-truth DB.
  mass_enumerate.py  cube-and-conquer orchestrator: resumable, checkpointed,
                     daemonizable, incremental nauty dedup + known-DB diff.
  build_known_db.py  fetch/parse Spence 6760 + Maksimovic 6, verify, canonicalise,
                     fingerprint, and compute the Seidel-switching closure.
  twograph_route.py  partition the DB into switching classes (regular two-graphs).
  properties_report.py  prints and writes the P1-P12 status report.
Tests/               pytest suite (encoder, iso, properties, twographs, backends).
Utilities/
  graphReader.py     seed adjacency-matrix reader.
  paley.py           Paley graph P(q) constructor (a real SRG(37,18,8,9)).
  kWriter.py cycleWriter.py pathWriter.py   seed generators (K_n, C_n, P_n).
ProcessFiles/
  known37/           ground-truth DB: *.g6 per source, all_canonical.g6 (6766),
                     switching_closure.g6 (6802), fingerprints/summary JSON.
output/              structured enumeration outputs:
                     srg_<v>_<k>_<lam>_<mu>/runs/<tag>/summary.json
                     srg_<v>_<k>_<lam>_<mu>/runs/<tag>/graphs.{g6,jsonl}
                     srg_<v>_<k>_<lam>_<mu>/campaigns/<tag>/...
                     srg_<v>_<k>_<lam>_<mu>/graphs/graphs.{g6,jsonl}
                     srg_<v>_<k>_<lam>_<mu>/summary.json
Output/              legacy artifacts kept for backward compatibility.
Vendor/sms/          the built SMS source tree (smsg installed to ~/.local/bin).
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # python-sat (bundles CaDiCaL)
brew install nauty cadical                        # or apt-get install nauty
```

Optional but recommended - build SMS (`smsg` + `pysms`) from the vendored
source (already patched for macOS):

```bash
cd Vendor/sms && ./build-and-install.sh -l -p /path/to/.venv/bin/pip
# installs smsg into ~/.local/bin and pysms into the venv
```

## Usage

Validate the whole pipeline (reproduces known non-isomorphic counts):

```bash
.venv/bin/python Automators/validate.py
```

Print the property (P1-P12) report:

```bash
.venv/bin/python Automators/properties_report.py
```

Enumerate a (small) SRG end-to-end:

```bash
.venv/bin/python Automators/enumerate.py --v 9 --k 4 --lam 1 --mu 2 --tag paley9
```

Bounded run on the open target (auto-selects smsg if available):

```bash
.venv/bin/python Automators/enumerate.py --limit 5 --timeout 300 --tag srg37
```

Multi-stage max-clique decomposition:

```bash
.venv/bin/python Automators/stage.py --anchors 3,4,5 --tag srg37_staged
```

Backends: `--backend {auto,smsg,pysat}` (default `auto`).
All automators accept `--out` to change the output root (default: `output`).

## Testing

```bash
.venv/bin/python -m pytest Tests/ -q          # unit tests (encoder/iso/props/...)
.venv/bin/python Automators/validate.py       # fast known-count matrix + DB
.venv/bin/python Automators/validate.py --full # adds SRG(25),(26),(29)
```

The **known-count matrix** runs the full encode -> ALL-SAT -> dedup pipeline and
checks the exact non-isomorphic counts from Brouwer's tables: C5, Paley(9),
Petersen, Paley(13), GQ(2,2), the two SRG(16,6,2,2), Clebsch, and (with
`--full`) the Paulus graphs (25,12,5,6)=15, (26,10,3,4)=10, and the conference
case (29,14,6,7)=41.  For the small cases both backends run and must **agree**.

## Ground-truth database

```bash
.venv/bin/python Automators/build_known_db.py   # builds ProcessFiles/known37/
```

Downloads Spence's 6760 and Maksimovic's 6 SRG(37,18,8,9), verifies **all** as
genuine SRGs, canonicalises them with nauty, and computes the **Seidel-switching
closure**.  Result (reproducible):

* 6760 (Spence) + 6 (Maksimovic) = **6766** distinct catalogued graphs;
* Spence's 6760 form exactly **191** switching classes (regular two-graphs on 38
  vertices) and are switching-closed - independently reproducing McKay-Spence;
* Maksimovic's 6 lie in **3 further** two-graphs; completing those classes adds
  **36** more graphs, giving a switching-closed **6802 graphs in 194 classes**
  (a new lower bound: >= 6802 SRG(37,18,8,9), >= 194 regular two-graphs on 38).

## Mass enumeration

Cube-and-conquer orchestrator (resumable / checkpointed / daemonizable):

```bash
# dress rehearsal on a fully-known case:
.venv/bin/python Automators/mass_enumerate.py --v 29 --k 14 --lam 6 --mu 7 \
    --cube-cutoff 24 --workers 8 --cube-timeout 600 --tag rehearsal29
# long unattended run that survives the launching shell (double-fork+setsid):
.venv/bin/python Automators/mass_enumerate.py ... --detach
# resume after interruption:
.venv/bin/python Automators/mass_enumerate.py --tag rehearsal29 --resume
# if the same tag exists under multiple SRG parameter sets, add --v/--k/--lam/--mu
```

Cubes are generated with `smsg --simple-assignment-cutoff` (their cover is
verified complete via `--cube-file-test`), solved independently with a per-cube
watchdog, canonicalised, checkpointed to `state.json`, incrementally merged into
a nauty-deduped `canonical.g6`, and diffed against the known DB.  Campaigns now
also emit `canonical.jsonl` (graph6 + adjacency matrix per graph) and detailed
`summary.json` metadata (counts, timing, completeness, artifact paths). Cubes
that exceed the watchdog are recorded as `timeout` (so `search_complete` is
never falsely reported) and are re-tried on `--resume`.

Two-graph / Seidel route (the (37) completeness route):

```bash
.venv/bin/python Automators/twograph_route.py   # switching-class partition + closure
```

## Status / expectations

Full enumeration of SRG(37,18,8,9) is an **open research problem**; a single
monolithic SAT run is not expected to finish. Established here:

* a **correct, validated, isomorph-free** pipeline (64 passing tests; exact
  known counts reproduced on both backends);
* a fully-verified **ground-truth DB** and, via Seidel switching, a **new
  switching-closed lower bound of 6802 graphs / 194 two-graphs** (the two-graph
  route), independently reproducing Spence's 191 as a validation;
* a resumable **cube-and-conquer** engine with verified-complete cube covers and
  honest completeness accounting.

**Known bottleneck.** The Sinz-counter SRG encoding is correct but heavy for SMS
*completeness*: even (29,14,6,7) does not finish quickly (a handful of
"interesting" cubes dominate). Direct SMS enumeration of (37) therefore needs a
leaner encoding and/or recursive sub-cubing of hard cubes; the two-graph route
(switching closure + enumerating regular two-graphs on 38 vertices) is the more
promising completeness path and is where the concrete new graphs came from.
