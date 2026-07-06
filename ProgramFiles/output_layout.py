"""Shared output layout + graph artifact helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import glob
import json
import os
from typing import Iterable, Optional, Sequence

import iso


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_output_root(project_root: str, output_root: str = "output") -> str:
    if os.path.isabs(output_root):
        return output_root
    return os.path.join(project_root, output_root)


def spec_params(spec) -> Sequence[int]:
    return [int(spec.V), int(spec.degree), int(spec.lam), int(spec.mu)]


def srg_id(spec) -> str:
    v, k, lam, mu = spec_params(spec)
    return f"srg_{v}_{k}_{lam}_{mu}"


def srg_dir(spec, output_root: str) -> str:
    return os.path.join(output_root, srg_id(spec))


def run_dir(spec, output_root: str, tag: str) -> str:
    return os.path.join(srg_dir(spec, output_root), "runs", tag)


def campaign_dir(spec, output_root: str, tag: str) -> str:
    return os.path.join(srg_dir(spec, output_root), "campaigns", tag)


def legacy_campaign_dir(project_root: str, tag: str) -> str:
    return os.path.join(project_root, "Output", f"campaign_{tag}")


def discover_campaign_dirs(output_root: str, tag: str) -> list[str]:
    pattern = os.path.join(output_root, "srg_*", "campaigns", tag)
    out = []
    for path in sorted(glob.glob(pattern)):
        if os.path.exists(os.path.join(path, "config.json")):
            out.append(path)
    return out


def read_g6(path: str) -> list[str]:
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return [ln.strip() for ln in fh if ln.strip()]


def atomic_write_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=2)
    os.replace(tmp, path)


def write_graph_artifacts(
    graph6_lines: Iterable[str],
    g6_path: str,
    jsonl_path: str,
    *,
    source: Optional[str] = None,
    tag: Optional[str] = None,
) -> None:
    lines = [g.strip() for g in graph6_lines if g and g.strip()]
    os.makedirs(os.path.dirname(g6_path), exist_ok=True)
    with open(g6_path, "w") as fh:
        fh.write("\n".join(lines) + ("\n" if lines else ""))
    with open(jsonl_path, "w") as fh:
        for idx, g6 in enumerate(lines, start=1):
            rec = {
                "index": idx,
                "graph6": g6,
                "adjacency_matrix": iso.graph6_to_matrix(g6),
            }
            if source is not None:
                rec["source"] = source
            if tag is not None:
                rec["tag"] = tag
            fh.write(json.dumps(rec) + "\n")


def catalog_paths(spec, output_root: str) -> tuple[str, str]:
    graphs_dir = os.path.join(srg_dir(spec, output_root), "graphs")
    return (
        os.path.join(graphs_dir, "graphs.g6"),
        os.path.join(graphs_dir, "graphs.jsonl"),
    )


def replace_srg_catalog(
    spec,
    output_root: str,
    graph6_lines: Iterable[str],
    *,
    source: str,
    tag: str,
) -> dict:
    g6_path, jsonl_path = catalog_paths(spec, output_root)
    lines = [g.strip() for g in graph6_lines if g and g.strip()]
    write_graph_artifacts(lines, g6_path, jsonl_path, source=source, tag=tag)
    return {
        "catalog_g6": g6_path,
        "catalog_jsonl": jsonl_path,
        "total_graphs": len(lines),
        "new_graphs": len(lines),
        "replaced": True,
    }


def upsert_srg_catalog(
    spec,
    output_root: str,
    graph6_lines: Iterable[str],
    *,
    source: str,
    tag: str,
) -> dict:
    g6_path, jsonl_path = catalog_paths(spec, output_root)
    existing = read_g6(g6_path)
    pool = set(existing)
    combined = list(existing)
    for g6 in graph6_lines:
        g = g6.strip()
        if not g or g in pool:
            continue
        pool.add(g)
        combined.append(g)
    write_graph_artifacts(combined, g6_path, jsonl_path, source=source, tag=tag)
    return {
        "catalog_g6": g6_path,
        "catalog_jsonl": jsonl_path,
        "total_graphs": len(combined),
        "new_graphs": len(combined) - len(existing),
        "replaced": False,
    }


def is_authoritative_full_enum(
    *,
    search_complete: bool,
    fix_clique: int = 0,
    forbid_clique=None,
    forbid_independent=None,
    limit=None,
) -> bool:
    """True when a run covers the full unconstrained search space."""
    return (
        search_complete
        and limit is None
        and fix_clique == 0
        and forbid_clique is None
        and forbid_independent is None
    )


def publish_run_artifacts(
    spec,
    output_root: str,
    *,
    tag: str,
    run_dir_path: str,
    graph6_lines: Sequence[str],
    summary: dict,
    source: str = "run",
    search_complete: bool = False,
    authoritative_full_enum: bool = False,
) -> dict:
    """Persist every artifact for one run under its SRG output directory."""
    g6_path = os.path.join(run_dir_path, "graphs.g6")
    jsonl_path = os.path.join(run_dir_path, "graphs.jsonl")
    write_graph_artifacts(
        graph6_lines, g6_path, jsonl_path, source=source, tag=tag
    )

    if authoritative_full_enum:
        catalog = replace_srg_catalog(
            spec, output_root, graph6_lines, source=source, tag=tag
        )
    else:
        catalog = upsert_srg_catalog(
            spec, output_root, graph6_lines, source=source, tag=tag
        )

    summary_path = os.path.join(run_dir_path, "summary.json")
    artifacts = summary.setdefault("artifacts", {})
    artifacts.update(
        {
            "run_dir": run_dir_path,
            "graphs_g6": g6_path,
            "graphs_jsonl": jsonl_path,
            "catalog_g6": catalog["catalog_g6"],
            "catalog_jsonl": catalog["catalog_jsonl"],
            "summary_json": summary_path,
        }
    )
    summary["output_g6"] = g6_path
    summary["output_jsonl"] = jsonl_path
    atomic_write_json(summary_path, summary)

    update_srg_summary(
        spec,
        output_root,
        run_entry={
            "tag": tag,
            "engine": summary.get("engine", source),
            "run_dir": run_dir_path,
            "search_complete": search_complete,
            "valid_srgs": summary.get("valid_srgs", len(graph6_lines)),
            "seconds": summary.get("seconds"),
            "summary_json": summary_path,
        },
    )
    return {
        "run_g6": g6_path,
        "run_jsonl": jsonl_path,
        "summary_json": summary_path,
        **catalog,
    }


def summary_path(spec, output_root: str) -> str:
    return os.path.join(srg_dir(spec, output_root), "summary.json")


def update_srg_summary(
    spec,
    output_root: str,
    *,
    run_entry: Optional[dict] = None,
    campaign_entry: Optional[dict] = None,
) -> dict:
    path = summary_path(spec, output_root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        with open(path) as fh:
            data = json.load(fh)
    else:
        data = {
            "schema_version": 2,
            "srg_id": srg_id(spec),
            "params": list(spec_params(spec)),
            "runs": {},
            "campaigns": {},
        }
    data["schema_version"] = 2
    data["srg_id"] = srg_id(spec)
    data["params"] = list(spec_params(spec))
    if run_entry is not None:
        data.setdefault("runs", {})[run_entry["tag"]] = run_entry
    if campaign_entry is not None:
        data.setdefault("campaigns", {})[campaign_entry["tag"]] = campaign_entry
    g6_path, jsonl_path = catalog_paths(spec, output_root)
    data["graph_catalog"] = {
        "g6_path": g6_path,
        "jsonl_path": jsonl_path,
        "total_graphs": len(read_g6(g6_path)),
    }
    data["updated_at"] = utc_now_iso()
    atomic_write_json(path, data)
    return data
