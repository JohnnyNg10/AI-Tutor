"""
AI Tutor 评测主入口

用法:
  # 完整评测 (全部画像 × 全部轨迹)
  python -m evaluation.run_evaluation

  # 快速评测 (仅 P1/P3 × T1/T2，10题)
  python -m evaluation.run_evaluation --quick

  # 仅计算指标 (从已有结果文件)
  python -m evaluation.run_evaluation --results results.json

  # 指定后端地址
  EVAL_BASE_URL=http://localhost:8000 python -m evaluation.run_evaluation
"""

import asyncio
import json
import os
import sys
import time

# 修复 Windows GBK 控制台编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.profiles import PROFILES
from evaluation.trajectories import TRAJECTORIES
from evaluation.simulator import run_all_simulations, SimulationResult
from evaluation.metrics_engine import MetricsEngine, MetricResult
from evaluation.badcase_detector import BadCaseDetector
from evaluation.report_generator import ReportGenerator


def serialize_results(results: list) -> list:
    """序列化 SimulationResult 列表"""
    return [r if isinstance(r, dict) else r.to_dict() for r in results]


def print_header(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def print_dimension_health(dimension_summary: dict):
    """打印六维健康仪表盘"""
    print("\n  ┌─ 六维健康仪表盘" + "─" * 40)
    print(f"  │ {'维度':　<10} {'健康率':>6}  {'P0':>4} {'P1':>4} {'状态'}")
    print(f"  ├{'─' * 52}")
    for dim in ["推荐质量", "教学效果", "认知诊断", "用户体验", "个性化", "鲁棒性"]:
        d = dimension_summary.get(dim, {})
        health = d.get("health", "?")
        icon = {"healthy": "+", "warning": "~", "critical": "!"}.get(health, "?")
        print(f"  │ [{icon}] {dim:　<8} {d.get('good_rate', 0):>5.0%}  "
              f"{d.get('warn_count', 0):>4} {d.get('critical_count', 0):>4} "
              f"{health}")
    print(f"  └{'─' * 52}")


async def main():
    import argparse
    parser = argparse.ArgumentParser(description="AI Tutor 评测引擎")
    parser.add_argument("--quick", action="store_true", help="快速评测模式")
    parser.add_argument("--profiles", type=str, default=None, help="画像列表，逗号分隔 (P1,P2,P3,P4,P5)")
    parser.add_argument("--trajectories", type=str, default=None, help="轨迹列表，逗号分隔 (T1,T2,T3,T4)")
    parser.add_argument("--questions", type=int, default=30, help="每个轨迹题目数")
    parser.add_argument("--results", type=str, default=None, help="从已有结果文件加载")
    parser.add_argument("--output", type=str, default=None, help="输出目录")
    args = parser.parse_args()

    t_start = time.time()

    # ── 1. 运行模拟 ────────────────────────────────────
    print_header("AI Tutor 评测引擎")

    if args.results:
        print(f"\n  从文件加载结果: {args.results}")
        with open(args.results, "r", encoding="utf-8") as f:
            raw_results = json.load(f)
    else:
        if args.quick:
            profiles_list = ["P1", "P3"]
            traj_list = ["T1", "T2"]
            n_q = 10
            print("\n  快速评测模式: P1/P3 × T1/T2 × 10题")
        else:
            profiles_list = args.profiles.split(",") if args.profiles else list(PROFILES.keys())
            traj_list = args.trajectories.split(",") if args.trajectories else list(TRAJECTORIES.keys())
            n_q = args.questions
            print(f"\n  完整评测模式: {len(profiles_list)}画像 × {len(traj_list)}轨迹 × {n_q}题")

        print(f"  后端地址: {os.getenv('EVAL_BASE_URL', 'http://localhost:8000')}")
        print(f"  预计用例: {len(profiles_list) * len(traj_list)} 条轨迹\n")

        try:
            results = await run_all_simulations(
                profiles=profiles_list,
                trajectories=traj_list,
                n_questions=n_q,
            )
        except Exception as e:
            print(f"\n  ❌ 模拟失败: {e}")
            print("  提示: 请确保后端服务正在运行 (start.bat)")
            return

        raw_results = serialize_results(results)

        # 保存结果
        os.makedirs("evaluation/results", exist_ok=True)
        result_path = f"evaluation/results/sim_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(raw_results, f, indent=2, ensure_ascii=False)
        print(f"\n  结果已保存: {result_path}")

    # ── 2. 计算指标 ────────────────────────────────────
    print_header("指标计算")

    engine = MetricsEngine()
    engine.load_results(raw_results)
    metrics = engine.calculate_all(verbose=True)
    dim_summary = engine.summary_by_dimension()
    global_score = engine.global_health_score()

    print(f"\n  全局健康分: {global_score}/100")

    # ── 3. Bad Case 检测 ────────────────────────────────
    print_header("Bad Case 检测")

    detector = BadCaseDetector()

    # 按 profile/trajectory 分组检测
    metrics_by_key = {}
    for result in raw_results:
        key = f"{result.get('profile_id', '?')}/{result.get('trajectory_id', '?')}"
        # 计算该结果的指标
        e2 = MetricsEngine()
        e2.load_results([result])
        m2 = e2.calculate_all()
        if key not in metrics_by_key:
            metrics_by_key[key] = []
        metrics_by_key[key].extend(m2)

    bad_cases = detector.scan_all(metrics_by_key)
    bc_summary = detector.summary()

    print(f"\n  发现 {bc_summary['total_cases']} 个 Bad Case")
    print(f"  P0(紧急): {bc_summary['p0_count']} | P1(重要): {bc_summary['p1_count']} | P2(优化): {bc_summary['p2_count']}")

    # ── 4. 六维健康仪表盘 ────────────────────────────────
    print_dimension_health(dim_summary)

    # ── 5. 生成报告 ────────────────────────────────────
    print_header("生成报告")

    report_gen = ReportGenerator(args.output)
    report = report_gen.generate(
        metrics=metrics,
        bad_cases=bad_cases,
        dimension_summary=dim_summary,
        global_score=global_score,
        run_metadata={
            "模拟用户数": len(raw_results),
            "总答题数": sum(r.get("actions_count", 0) for r in raw_results),
            "Bad Case 数": len(bad_cases),
            "总耗时": f"{time.time() - t_start:.1f}s",
        },
    )

    print(f"\n  报告已保存至: {report_gen.output_dir}")
    print(f"\n{'=' * 60}")
    print(f"  评测完成! 全局健康分: {global_score}/100")
    if bc_summary["needs_immediate_action"]:
        print(f"  ⚠️  发现 P0 级 Bad Case，建议立即处理!")
    print(f"{'=' * 60}\n")

    return {
        "global_score": global_score,
        "dimension_summary": dim_summary,
        "bad_case_summary": bc_summary,
        "metrics": [{"name": m.name, "value": m.value, "status": m.status} for m in metrics],
    }


if __name__ == "__main__":
    summary = asyncio.run(main())
