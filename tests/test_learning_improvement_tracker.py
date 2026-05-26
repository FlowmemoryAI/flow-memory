from flow_memory.learning.improvement_tracker import ImprovementTracker


def test_improvement_tracker_reports_before_after_metrics() -> None:
    tracker = ImprovementTracker()
    tracker.add("memory_records", 0.0, 2.0)
    tracker.add("error_rate", 0.5, 0.1, higher_is_better=False)
    summary = tracker.summary()
    assert summary["ok"] is True
    assert len(summary["metrics"]) == 2
