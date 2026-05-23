from flow_memory.self_improvement import HealthMonitor, RepairPlanner


report = HealthMonitor().assess(rate_limited=True, quality_score=0.1, failed_tests=("tests/test_demo.py",))
plan = RepairPlanner().plan(report)
print({"flags": sorted(report.flags), "requires_approval": plan.requires_approval, "steps": [step.action for step in plan.steps]})
