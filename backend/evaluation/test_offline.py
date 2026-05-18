"""离线自检 - 不需要后端运行即可验证评测引擎"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.profiles import PROFILES
from evaluation.trajectories import TRAJECTORIES, TrajectoryGenerator
from evaluation.metrics_engine import MetricsEngine
from evaluation.badcase_detector import BadCaseDetector, BadCase
from evaluation.report_generator import ReportGenerator


def test_trajectory_generation():
    """测试轨迹生成"""
    print("=" * 50)
    print("1. 轨迹生成测试")
    for pid, p in PROFILES.items():
        for tid, tinfo in TRAJECTORIES.items():
            gen = TrajectoryGenerator(p, seed=hash(f"{pid}_{tid}") % 10000)
            diffs = [(i % 5) + 1 for i in range(30)]
            actions = gen.generate(tinfo["type"], diffs)
            correct = sum(1 for a in actions if a.is_correct)
            hints = sum(1 for a in actions if a.hint_count > 0)
            skips = sum(1 for a in actions if a.skip_reason)
            tag = "OK" if 0 < correct < 30 else "EDGE"
            print(f"  [{pid}/{tid}] {tinfo['name']:<6s} {correct:>2}/30 correct"
                  f"  {hints:>2}hints  {skips:>2}skips  [{tag}]")


def test_metrics_engine():
    """测试指标计算"""
    print("\n" + "=" * 50)
    print("2. 指标计算测试")
    # 构建模拟数据
    results = []
    for pid in ["P1", "P3"]:
        for tid in ["T1", "T2"]:
            results.append({
                "profile_id": pid,
                "trajectory_id": tid,
                "actions_count": 30,
                "feedbacks_count": 28,
                "theta_trajectory": [-2.0, -1.8, -1.6, -1.5, -1.3, -1.2] if pid == "P1" else [0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                "mastery_trajectory": [0.2, 0.25, 0.3, 0.35, 0.4, 0.42] if pid == "P1" else [0.5, 0.55, 0.6, 0.65, 0.68, 0.72],
                "feedbacks": [
                    {"is_correct": i % 2 == 0, "hint_count": i % 3, "avg_mastery": 0.5 + i * 0.01}
                    for i in range(28)
                ],
                "_raw_recommendations": [
                    {"questions": [{"difficulty": (i % 5) + 1, "knowledge_points": [f"kp_{i % 10}"]}]}
                    for i in range(28)
                ],
                "_raw_actions": [
                    {"is_correct": i % 2 == 0, "hint_count": i % 3}
                    for i in range(30)
                ],
            })

    engine = MetricsEngine()
    engine.load_results(results)
    metrics = engine.calculate_all(verbose=True)

    summary = engine.summary_by_dimension()
    score = engine.global_health_score()
    print(f"\n  全局健康分: {score}/100")

    ok_count = sum(1 for m in metrics if m.status == "good")
    print(f"  Good: {ok_count}/{len(metrics)} | "
          f"Warn: {sum(1 for m in metrics if m.status == 'warn')} | "
          f"Critical: {sum(1 for m in metrics if m.status == 'critical')}")
    assert ok_count > 0, "At least some metrics should be good"


def test_badcase_detection():
    """测试 Bad Case 检测"""
    print("\n" + "=" * 50)
    print("3. Bad Case 检测测试")

    from evaluation.metrics_engine import MetricResult
    # 构造一个会触发规则的指标
    test_metrics = [
        MetricResult("难度匹配度", "推荐质量", "L2", 2.0, 0.8, 1.5, "critical", "test"),
        MetricResult("提示有效率", "教学效果", "L2", 0.2, 0.55, 0.35, "critical", "test"),
        MetricResult("BKT收敛速度", "认知诊断", "L2", 5, 8, 15, "good", "test"),
    ]

    detector = BadCaseDetector()
    cases = detector.scan(test_metrics, "P1", "T2")
    for c in cases:
        print(f"  [{c.severity}] {c.title}: {c.phenomenon[:50]}...")
    assert len(cases) >= 2, f"Expected at least 2 bad cases, got {len(cases)}"
    print(f"  Detected {len(cases)} bad cases - OK")


def test_report_generation():
    """测试报告生成"""
    print("\n" + "=" * 50)
    print("4. 报告生成测试")

    from evaluation.metrics_engine import MetricResult
    metrics = [
        MetricResult("难度匹配度", "推荐质量", "L2", 0.6, 0.8, 1.5, "good", "test"),
        MetricResult("提示有效率", "教学效果", "L2", 0.7, 0.55, 0.35, "good", "test"),
    ]
    bad_cases = [
        BadCase(
            case_id="BC-0001", title="测试Case", rule_name="test_rule",
            severity="P1", dimension="推荐质量", profile_id="P1", trajectory_id="T2",
            trigger_metric="难度匹配度", trigger_value=2.0, trigger_threshold=1.5,
            phenomenon="测试现象", root_cause_hints=["可能原因1", "可能原因2"],
            affected_user_types=["P1"], suggested_fix="测试修复方案"
        )
    ]
    dim_summary = {
        "推荐质量": {"metric_count": 1, "good_rate": 1.0, "warn_count": 0, "critical_count": 0, "health": "healthy"},
        "教学效果": {"metric_count": 1, "good_rate": 1.0, "warn_count": 0, "critical_count": 0, "health": "healthy"},
    }

    gen = ReportGenerator()
    report = gen.generate(metrics, bad_cases, dim_summary, 85.0, {"test": "yes"})
    assert "AI Tutor 评测报告" in report
    assert "BC-0001" in report
    print(f"  报告生成成功, {len(report)} 字符")


if __name__ == "__main__":
    test_trajectory_generation()
    test_metrics_engine()
    test_badcase_detection()
    test_report_generation()
    print("\n" + "=" * 50)
    print("All offline tests passed!")
