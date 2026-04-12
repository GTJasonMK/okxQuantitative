from app.core.trend_research.training_tracker import TrendTrainingTracker


def test_tracker_records_stage_progress_and_epoch_history():
    tracker = TrendTrainingTracker()
    run = tracker.start_run(lookback=3600, total_epochs=20)

    tracker.start_stage("collect_bars", message="collecting bars")
    tracker.finish_stage(
        "collect_bars",
        stats={"eligible_inst_count": 3, "inst_count": 5},
    )
    tracker.start_stage("train_epochs", message="Epoch 1 / 20")
    stage_start_progress = tracker.snapshot()["progress_pct"]
    tracker.record_epoch(
        epoch=1,
        total_epochs=20,
        train_loss=0.84,
        validation_loss=0.91,
    )

    snapshot = tracker.snapshot()
    assert snapshot["run_id"] == run["run_id"]
    assert snapshot["status"] == "running"
    assert snapshot["current_stage"] == "train_epochs"
    assert snapshot["stages"][1]["stage"] == "collect_bars"
    assert snapshot["stages"][1]["status"] == "completed"
    assert snapshot["stages"][1]["stats"]["eligible_inst_count"] == 3
    assert snapshot["progress_pct"] >= stage_start_progress
    assert snapshot["stages"][5]["stats"]["current_epoch"] == 1
    assert snapshot["stages"][5]["stats"]["total_epochs"] == 20
    assert snapshot["stages"][5]["stats"]["latest_validation_loss"] == 0.91
    assert snapshot["epoch_history"][0]["epoch"] == 1
    assert snapshot["epoch_history"][0]["validation_loss"] == 0.91


def test_tracker_keeps_failed_run_visible():
    tracker = TrendTrainingTracker()
    tracker.start_run(lookback=3600, total_epochs=20)
    tracker.start_stage("build_samples", message="building")
    tracker.fail_run(
        "build_samples",
        "insufficient local bars for direct extrema training",
    )

    snapshot = tracker.snapshot()
    assert snapshot["status"] == "failed"
    assert snapshot["current_stage"] == "build_samples"
    assert snapshot["error_message"] == "insufficient local bars for direct extrema training"
    assert snapshot["stages"][3]["status"] == "failed"
