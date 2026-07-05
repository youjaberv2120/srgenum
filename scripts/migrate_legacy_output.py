"""One-time migration: fold pre-restructure `Output/` artifacts into the
per-SRG layout (`output/srg_<v>_<k>_<lam>_<mu>/...`).

Behavior:
  * For every legacy `<tag>.g6` (+ matching `<tag>.json` when present) whose
    filename encodes an SRG parameter set, materialize a proper run folder
    under `output/srg_.../runs/legacy_<tag>/` with `graphs.g6`,
    `graphs.jsonl`, and a `summary.json` that annotates the source file.
  * Merge every legacy graph6 line into the per-SRG catalog under
    `graphs/graphs.{g6,jsonl}` so all previously enumerated graphs remain
    accessible through the new interface.
  * Move each pre-existing `Output/campaign_<tag>/` under
    `output/srg_<...>/campaigns/<tag>/` (keeping its internal layout).
  * Move ad-hoc scripts / logs / stray CNFs / cube seeds / experimental g6
    outputs under `output/_legacy_archive/` so nothing valuable is lost while
    the top-level Output folder is cleaned up.
  * Refresh each affected `srg_.../summary.json` via `output_layout`.

Rerunning is idempotent for the per-SRG catalog (dedups by graph6 line).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "ProgramFiles")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import iso  # noqa: E402
from srg_encoder import SRGSpec  # noqa: E402
from output_layout import (  # noqa: E402
    campaign_dir as campaign_path_for_spec,
    resolve_output_root,
    run_dir,
    srg_dir,
    update_srg_summary,
    upsert_srg_catalog,
    utc_now_iso,
    write_graph_artifacts,
)


OUTPUT_ROOT = resolve_output_root(_ROOT, "output")
LEGACY_DIR = OUTPUT_ROOT  # macOS case-insensitive: Output/ and output/ are the same
ARCHIVE = os.path.join(OUTPUT_ROOT, "_legacy_archive")


PARAM_RE = re.compile(r"(?P<v>\d+)_(?P<k>\d+)_(?P<lam>\d+)_(?P<mu>\d+)")


# Explicit mapping for legacy tags that don't carry SRG params in their name.
TAG_TO_PARAMS = {
    "c5": (5, 2, 0, 1),
    "c5_smsg": (5, 2, 0, 1),
    "auto_p9": (9, 4, 1, 2),
    "p9_smsg": (9, 4, 1, 2),
    "stage_p9_all": (9, 4, 1, 2),
    "stage_p9_k3": (9, 4, 1, 2),
    "stage_p9_k4": (9, 4, 1, 2),
    "stage_p9_summary": (9, 4, 1, 2),
    "srg37_demo": (37, 18, 8, 9),
}


def _spec(params):
    v, k, lam, mu = params
    return SRGSpec(int(v), int(k), int(lam), int(mu))


def _params_from_filename(basename: str):
    """Try to recover (v,k,lam,mu) from a legacy filename."""
    stem = basename
    for ext in (".g6", ".json", ".cnf"):
        if stem.endswith(ext):
            stem = stem[: -len(ext)]
            break
    if stem in TAG_TO_PARAMS:
        return TAG_TO_PARAMS[stem]
    m = PARAM_RE.search(stem)
    if m:
        return int(m["v"]), int(m["k"]), int(m["lam"]), int(m["mu"])
    return None


def _read_g6(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except json.JSONDecodeError:
        return None


def _archive(path):
    os.makedirs(ARCHIVE, exist_ok=True)
    dest = os.path.join(ARCHIVE, os.path.basename(path))
    if os.path.exists(dest):
        base, ext = os.path.splitext(dest)
        i = 1
        while os.path.exists(f"{base}_{i}{ext}"):
            i += 1
        dest = f"{base}_{i}{ext}"
    shutil.move(path, dest)
    return dest


def migrate_flat_g6_json(basename):
    """Migrate `<basename>.g6` (+ `.json`) under Output/ into new layout."""
    g6_path = os.path.join(LEGACY_DIR, basename + ".g6")
    json_path = os.path.join(LEGACY_DIR, basename + ".json")
    if not os.path.exists(g6_path) and not os.path.exists(json_path):
        return None

    params = _params_from_filename(basename)
    if params is None:
        # Cannot classify — archive both.
        if os.path.exists(g6_path):
            _archive(g6_path)
        if os.path.exists(json_path):
            _archive(json_path)
        return None

    spec = _spec(params)
    tag = f"legacy_{basename}"
    dest_run = run_dir(spec, OUTPUT_ROOT, tag)
    os.makedirs(dest_run, exist_ok=True)

    lines = _read_g6(g6_path)
    dest_g6 = os.path.join(dest_run, "graphs.g6")
    dest_jsonl = os.path.join(dest_run, "graphs.jsonl")
    write_graph_artifacts(lines, dest_g6, dest_jsonl,
                          source="legacy", tag=basename)

    orig_json = _read_json(json_path) or {}
    catalog = upsert_srg_catalog(
        spec, OUTPUT_ROOT, lines, source="legacy", tag=basename
    )
    summary = {
        "schema_version": 2,
        "tag": tag,
        "source_basename": basename,
        "params": list(params),
        "migrated_at": utc_now_iso(),
        "valid_srgs": len(lines),
        "search_complete": bool(orig_json.get("search_complete", True))
        if isinstance(orig_json, dict) else True,
        "artifacts": {
            "run_dir": dest_run,
            "graphs_g6": dest_g6,
            "graphs_jsonl": dest_jsonl,
            "catalog_g6": catalog["catalog_g6"],
            "catalog_jsonl": catalog["catalog_jsonl"],
        },
        "original_summary": orig_json,
    }
    summary_path = os.path.join(dest_run, "summary.json")
    summary["artifacts"]["summary_json"] = summary_path
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    update_srg_summary(
        spec, OUTPUT_ROOT,
        run_entry={
            "tag": tag,
            "engine": (orig_json.get("engine") if isinstance(orig_json, dict) else None)
                       or "legacy",
            "run_dir": dest_run,
            "search_complete": summary["search_complete"],
            "valid_srgs": len(lines),
            "summary_json": summary_path,
            "type": "legacy",
        },
    )

    if os.path.exists(g6_path):
        os.remove(g6_path)
    if os.path.exists(json_path):
        os.remove(json_path)
    return {"tag": tag, "graphs": len(lines), "srg_id": f"srg_{params[0]}_{params[1]}_{params[2]}_{params[3]}"}


def migrate_stage_summary(basename):
    """Handle stage_*_summary.json (no graphs of its own)."""
    json_path = os.path.join(LEGACY_DIR, basename + ".json")
    if not os.path.exists(json_path):
        return None
    params = _params_from_filename(basename)
    if params is None:
        _archive(json_path)
        return None
    spec = _spec(params)
    dest_run = run_dir(spec, OUTPUT_ROOT, f"legacy_{basename}")
    os.makedirs(dest_run, exist_ok=True)
    dest = os.path.join(dest_run, "summary.json")
    shutil.move(json_path, dest)
    update_srg_summary(
        spec, OUTPUT_ROOT,
        run_entry={
            "tag": f"legacy_{basename}",
            "engine": "legacy",
            "run_dir": dest_run,
            "search_complete": True,
            "valid_srgs": None,
            "summary_json": dest,
            "type": "legacy_staged_summary",
        },
    )
    return {"tag": basename}


def migrate_campaign_dir(camp_dir):
    """Move Output/campaign_<tag> → output/srg_<...>/campaigns/<tag>/."""
    cfg_path = os.path.join(camp_dir, "config.json")
    cfg = _read_json(cfg_path) or {}
    params = cfg.get("params")
    if not params or len(params) != 4:
        # try to infer from name
        base = os.path.basename(camp_dir)
        m = re.search(r"29", base)
        if m:
            params = [29, 14, 6, 7]
        else:
            _archive(camp_dir)
            return None
    spec = _spec(params)
    base_tag = os.path.basename(camp_dir)
    if base_tag.startswith("campaign_"):
        tag = base_tag[len("campaign_"):]
    else:
        tag = base_tag
    dest = campaign_path_for_spec(spec, OUTPUT_ROOT, tag)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.move(camp_dir, dest)

    canon = os.path.join(dest, "canonical.g6")
    canon_jsonl = os.path.join(dest, "canonical.jsonl")
    lines = _read_g6(canon)
    if lines:
        write_graph_artifacts(lines, canon, canon_jsonl,
                              source="campaign", tag=tag)
        upsert_srg_catalog(spec, OUTPUT_ROOT, lines,
                           source="campaign", tag=tag)

    if os.path.exists(cfg_path):
        cfg = _read_json(cfg_path) or {}
    cfg["campaign_tag"] = tag
    cfg["srg_id"] = f"srg_{spec.V}_{spec.degree}_{spec.lam}_{spec.mu}"
    cfg["campaign_dir"] = dest
    cfg["output_root"] = OUTPUT_ROOT
    cfg.setdefault("schema_version", 2)
    with open(os.path.join(dest, "config.json"), "w") as fh:
        json.dump(cfg, fh, indent=1)

    summary_path = os.path.join(dest, "summary.json")
    summary = _read_json(summary_path) or {}
    summary.update({
        "schema_version": 2,
        "tag": tag,
        "srg_id": cfg["srg_id"],
        "campaign_dir": dest,
        "migrated_at": utc_now_iso(),
        "distinct_graphs": len(set(lines)) if lines else 0,
        "artifacts": {
            "summary_json": summary_path,
            "canonical_g6": canon,
            "canonical_jsonl": canon_jsonl,
            "state_json": os.path.join(dest, "state.json"),
            "config_json": os.path.join(dest, "config.json"),
            "cubes_txt": os.path.join(dest, "cubes.txt"),
            "formula_cnf": os.path.join(dest, "formula.cnf"),
        },
    })
    with open(summary_path, "w") as fh:
        json.dump(summary, fh, indent=2)

    update_srg_summary(
        spec, OUTPUT_ROOT,
        campaign_entry={
            "tag": tag,
            "campaign_dir": dest,
            "search_complete": bool(summary.get("search_complete", False)),
            "distinct_graphs": summary.get("distinct_graphs", 0),
            "summary_json": summary_path,
            "type": "legacy_campaign",
        },
    )
    return {"tag": tag, "dest": dest, "graphs": len(lines)}


def move_to_archive(pattern):
    for path in glob.glob(pattern):
        if os.path.isdir(path):
            continue
        _archive(path)


def collect_orphan_graphs():
    """Fold `_closed6802.g6` / `_escapes.g6` (SRG(37) descendants) into the
    catalog for srg_37_18_8_9. Looks in both the live Output/ dir and the
    archive (so this is safe to rerun)."""
    spec = SRGSpec(37, 18, 8, 9)
    for name in ("_closed6802.g6", "_escapes.g6"):
        for src in (
            os.path.join(LEGACY_DIR, name),
            os.path.join(ARCHIVE, name),
        ):
            if not os.path.exists(src):
                continue
            lines = _read_g6(src)
            if lines:
                upsert_srg_catalog(spec, OUTPUT_ROOT, lines,
                                   source="legacy_flat", tag=name)
            if os.path.dirname(src) == LEGACY_DIR:
                _archive(src)
            break
    update_srg_summary(spec, OUTPUT_ROOT)


def main():
    print("== migrating legacy flat validate_/cm_/etc. files ==")
    # discover any basename with a .g6 or .json at top level
    seen = set()
    for path in sorted(glob.glob(os.path.join(LEGACY_DIR, "*.g6"))):
        base = os.path.basename(path)[:-3]
        seen.add(base)
        res = migrate_flat_g6_json(base)
        if res:
            print(f"  {base} -> {res['srg_id']} ({res['graphs']} graphs)")
    for path in sorted(glob.glob(os.path.join(LEGACY_DIR, "*.json"))):
        base = os.path.basename(path)[:-5]
        if base in seen:
            continue
        # summary/stage jsons without accompanying .g6
        if base.startswith("stage_"):
            migrate_stage_summary(base)
        else:
            res = migrate_flat_g6_json(base)
            if res:
                print(f"  {base} (json only) -> {res['srg_id']}")

    print("\n== migrating legacy campaign_* directories ==")
    for camp in sorted(glob.glob(os.path.join(LEGACY_DIR, "campaign_*"))):
        if not os.path.isdir(camp):
            continue
        res = migrate_campaign_dir(camp)
        if res:
            print(f"  {os.path.basename(camp)} -> {res['dest']} ({res['graphs']} graphs)")

    print("\n== absorbing loose SRG(37)-related g6 into catalog ==")
    collect_orphan_graphs()

    print("\n== archiving remaining stray files ==")
    for pattern in (
        "*.cnf", "cubes*.txt", "_*.out", "_*.py",
        "properties_report.json", "build_known_db_full.log",
    ):
        move_to_archive(os.path.join(LEGACY_DIR, pattern))

    print("\nmigration complete.")


if __name__ == "__main__":
    main()
