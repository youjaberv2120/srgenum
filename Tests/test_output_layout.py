import json
import os

from srg_encoder import SRGSpec
from output_layout import (
    catalog_paths,
    is_authoritative_full_enum,
    publish_run_artifacts,
    read_g6,
    run_dir,
    summary_path,
    upsert_srg_catalog,
)


def _fake_g6(n: int) -> str:
    return "A" * n


def test_publish_run_artifacts_updates_all_srg_files(tmp_path):
    spec = SRGSpec(5, 2, 0, 1)
    output_root = str(tmp_path)
    tag = "demo"
    run = run_dir(spec, output_root, tag)
    os.makedirs(run, exist_ok=True)

    first = [_fake_g6(4), _fake_g6(5)]
    publish_run_artifacts(
        spec,
        output_root,
        tag=tag,
        run_dir_path=run,
        graph6_lines=first,
        summary={
            "schema_version": 2,
            "tag": tag,
            "engine": "test",
            "valid_srgs": len(first),
            "seconds": 1.0,
            "search_complete": True,
        },
        search_complete=True,
        authoritative_full_enum=True,
    )

    catalog_g6, catalog_jsonl = catalog_paths(spec, output_root)
    run_g6 = os.path.join(run, "graphs.g6")
    run_jsonl = os.path.join(run, "graphs.jsonl")
    run_summary = os.path.join(run, "summary.json")
    srg_summary = summary_path(spec, output_root)

    for path in (catalog_g6, catalog_jsonl, run_g6, run_jsonl, run_summary, srg_summary):
        assert os.path.exists(path), path

    assert read_g6(catalog_g6) == first
    assert read_g6(run_g6) == first

    with open(srg_summary) as fh:
        top = json.load(fh)
    assert top["runs"][tag]["valid_srgs"] == 2
    assert top["graph_catalog"]["total_graphs"] == 2

    second = [_fake_g6(6)]
    publish_run_artifacts(
        spec,
        output_root,
        tag=tag,
        run_dir_path=run,
        graph6_lines=second,
        summary={
            "schema_version": 2,
            "tag": tag,
            "engine": "test",
            "valid_srgs": len(second),
            "seconds": 2.0,
            "search_complete": True,
        },
        search_complete=True,
        authoritative_full_enum=True,
    )

    assert read_g6(run_g6) == second
    assert read_g6(catalog_g6) == second

    with open(run_summary) as fh:
        run_data = json.load(fh)
    assert run_data["valid_srgs"] == 1
    assert run_data["seconds"] == 2.0


def test_partial_run_upserts_catalog(tmp_path):
    spec = SRGSpec(5, 2, 0, 1)
    output_root = str(tmp_path)
    tag = "partial"
    run = run_dir(spec, output_root, tag)
    os.makedirs(run, exist_ok=True)

    upsert_srg_catalog(spec, output_root, [_fake_g6(3)], source="seed", tag="seed")
    publish_run_artifacts(
        spec,
        output_root,
        tag=tag,
        run_dir_path=run,
        graph6_lines=[_fake_g6(4)],
        summary={
            "schema_version": 2,
            "tag": tag,
            "engine": "test",
            "valid_srgs": 1,
            "seconds": 0.5,
            "search_complete": False,
        },
        search_complete=False,
        authoritative_full_enum=False,
    )

    catalog_g6, _ = catalog_paths(spec, output_root)
    assert read_g6(catalog_g6) == [_fake_g6(3), _fake_g6(4)]


def test_is_authoritative_full_enum():
    assert is_authoritative_full_enum(search_complete=True)
    assert not is_authoritative_full_enum(search_complete=False)
    assert not is_authoritative_full_enum(search_complete=True, limit=5)
    assert not is_authoritative_full_enum(search_complete=True, fix_clique=3)
