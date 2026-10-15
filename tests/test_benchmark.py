from real2scenario import (
    Actor,
    BenchmarkRun,
    Scenario,
    State,
    VariantReport,
    aggregate_benchmark_runs,
    aggregate_report,
    benchmark_aggregate_to_dict,
    evaluate_cp4_gates,
    validate_feasibility,
)


def _scenario(scenario_id: str) -> Scenario:
    return Scenario(
        scenario_id,
        1.0,
        "ego",
        (Actor("ego", "vehicle", (State(0.0, 0.0, 0.0, 0.0, 1.0), State(1.0, 1.0, 0.0, 0.0, 1.0))),),
        "local_road_aligned",
    )


def _run(run_id: str, scene_id: str, evidence_class: str, simulator: str) -> BenchmarkRun:
    scenario = _scenario(scene_id)
    validation = validate_feasibility(scenario)
    report = VariantReport(
        variant_id=f"{run_id}-variant",
        status="valid",
        scenario_artifact=f"{run_id}/scenario.json",
        xosc_artifact=None,
        replay_trace_artifact=None,
        report_artifact=f"{run_id}/report.json",
        validation=validation,
        gate_results=evaluate_cp4_gates(
            scenario,
            simulator_statuses={"esmini": "completed"},
            no_collision=True,
            diversity_distance=0.2,
        ),
    )
    return BenchmarkRun(
        run_id, scene_id, evidence_class, simulator,
        aggregate_report(scene_id, (report,)),
    )


def test_benchmark_aggregate_sorts_scenes_and_preserves_evidence_classes() -> None:
    aggregate = aggregate_benchmark_runs((
        _run("run-b", "scene-b", "nuscenes_local", "esmini"),
        _run("run-a", "scene-a", "synthetic", "none"),
    ))

    assert aggregate.scene_count == 2
    assert [item.scene_id for item in aggregate.scene_summaries] == ["scene-a", "scene-b"]
    assert aggregate.counts_by_evidence_class == {"nuscenes_local": 1, "synthetic": 1}
    assert aggregate.counts_by_simulator == {"esmini": 1, "none": 1}
    assert aggregate.status_counts == {"generated": 2, "valid": 2, "invalid": 0, "simulator_failed": 0}
    assert aggregate.scientific_status == "PROVISIONAL"


def test_benchmark_serialization_contains_provisional_funnel_and_no_paths() -> None:
    data = benchmark_aggregate_to_dict(
        aggregate_benchmark_runs((_run("run-a", "scene-a", "synthetic", "none"),))
    )

    assert data["benchmark_version"] == "benchmark-aggregate-v1"
    assert data["gate_funnel"]["scientific_status"] == "PROVISIONAL"
    assert data["status_counts"]["generated"] == 1
    assert "dataset_root" not in str(data)
    assert "scenario.json" not in str(data)


def test_benchmark_rejects_duplicate_scene_or_run_ids() -> None:
    run = _run("run-a", "scene-a", "synthetic", "none")

    try:
        aggregate_benchmark_runs((run, run))
    except ValueError as error:
        assert "run IDs" in str(error)
    else:
        raise AssertionError("duplicate benchmark run IDs must be rejected")

    duplicate_scene = _run("run-b", "scene-a", "synthetic", "none")
    try:
        aggregate_benchmark_runs((run, duplicate_scene))
    except ValueError as error:
        assert "scene IDs" in str(error)
    else:
        raise AssertionError("duplicate benchmark scene IDs must be rejected")
