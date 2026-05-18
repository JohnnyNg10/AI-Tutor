"""
22 项指标计算引擎

从模拟运行结果或数据库交互日志中提取指标。
所有指标返回 dict，包含 value / threshold / status / detail。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import math


@dataclass
class MetricResult:
    """单个指标计算结果"""
    name: str
    dimension: str
    level: str           # L1/L2/L3
    value: float
    threshold_good: float
    threshold_warn: float
    status: str          # "good" / "warn" / "critical"
    detail: str = ""
    raw_data: Any = None


class MetricsEngine:
    """指标计算引擎"""

    def __init__(self, simulation_results: List[Dict] = None):
        self.results = simulation_results or []
        self.metrics: List[MetricResult] = []

    def load_results(self, results: List[Dict]):
        self.results = results
        self.metrics = []

    # ── 推荐质量维度 ──────────────────────────────────────

    def _get_actions(self, result: Dict) -> list:
        """从多种可能字段中提取 actions"""
        actions = result.get("_raw_actions", [])
        if not actions:
            actions = result.get("actions", [])
        if not actions:
            # 从 feedbacks 重建
            feedbacks = result.get("_raw_feedbacks", result.get("feedbacks", []))
            actions = [{"is_correct": f.get("is_correct", False), "hint_count": f.get("hint_count", 0)}
                       for f in feedbacks]
        return actions

    def _get_recommendations(self, result: Dict) -> list:
        """从多种可能字段中提取 recommendations"""
        recs = result.get("_raw_recommendations", result.get("recommendations", []))
        # 如果 recs 是单个 dict，包装成列表
        if isinstance(recs, dict):
            recs = [recs]
        return recs

    def _extract_question_items(self, recs: list) -> list:
        """从推荐数据中提取题目列表（适配多种API返回格式）"""
        items = []
        for r in recs:
            if isinstance(r, dict):
                # 可能的 key: recommendations / questions / items
                inner = r.get("recommendations", r.get("questions", r.get("items", [])))
                if isinstance(inner, list):
                    items.extend(inner)
                elif isinstance(inner, dict):
                    items.append(inner)
        return items

    def calc_difficulty_match(self, result: Dict) -> MetricResult:
        """难度匹配度：推荐难度与用户 θ 的偏差"""
        theta_snap = result.get("theta_trajectory", [])
        recs = self._get_recommendations(result)
        items = self._extract_question_items(recs)
        diffs = [it.get("difficulty") for it in items if it.get("difficulty") is not None]

        if not theta_snap or not diffs:
            return MetricResult("难度匹配度", "推荐质量", "L2", -1, 0.8, 1.5, "unknown", "推荐数据未含difficulty字段")

        theta = sum(theta_snap) / len(theta_snap) if theta_snap else 0
        deviations = [abs(d - theta) for d in diffs[:len(theta_snap)]]
        avg_dev = sum(deviations) / len(deviations) if deviations else 999

        return MetricResult(
            name="难度匹配度",
            dimension="推荐质量",
            level="L2",
            value=round(avg_dev, 2),
            threshold_good=0.8,
            threshold_warn=1.5,
            status="good" if avg_dev <= 0.8 else ("warn" if avg_dev <= 1.5 else "critical"),
            detail=f"平均偏差={avg_dev:.2f}, theta={theta:.2f}",
        )

    def calc_coverage_rate(self, result: Dict) -> MetricResult:
        """知识点覆盖率：推荐去重题目数"""
        recs = self._get_recommendations(result)
        items = self._extract_question_items(recs)
        if not items:
            return MetricResult("知识点覆盖率", "推荐质量", "L3", -1, 0.6, 0.3, "unknown", "无推荐数据")

        unique_qs = set()
        for item in items:
            qid = item.get("question_id") or item.get("id")
            if qid:
                unique_qs.add(qid)

        coverage = len(unique_qs) / max(30, len(unique_qs) * 2) if unique_qs else 0
        coverage = min(1.0, coverage)

        return MetricResult(
            name="知识点覆盖率",
            dimension="推荐质量",
            level="L3",
            value=round(coverage, 2),
            threshold_good=0.6,
            threshold_warn=0.3,
            status="good" if coverage >= 0.6 else ("warn" if coverage >= 0.3 else "critical"),
            detail=f"{len(unique_qs)} 个不重复题目",
        )

    # ── 教学效果维度 ──────────────────────────────────────

    def calc_hint_effectiveness(self, result: Dict) -> MetricResult:
        """提示有效率：查看提示后答对的概率"""
        actions = self._get_actions(result)
        hinted = [a for a in actions if a.get("hint_count", 0) > 0]
        if not hinted:
            # 从原始 feedbacks 判断
            raw_fbs = result.get("_raw_feedbacks", result.get("feedbacks", []))
            if raw_fbs:
                fb_hinted = [f for f in raw_fbs if f.get("hint_count", 0) > 0]
                if not fb_hinted:
                    return MetricResult("提示有效率", "教学效果", "L2", 0, 0.55, 0.35, "good", "无提示使用(可能独立解题)")
            return MetricResult("提示有效率", "教学效果", "L2", -1, 0.55, 0.35, "unknown", "无提示使用记录")

        hinted_correct = sum(1 for a in hinted if a.get("is_correct", False))
        rate = hinted_correct / len(hinted)

        return MetricResult(
            name="提示有效率",
            dimension="教学效果",
            level="L2",
            value=round(rate, 2),
            threshold_good=0.55,
            threshold_warn=0.35,
            status="good" if rate >= 0.55 else ("warn" if rate >= 0.35 else "critical"),
            detail=f"{hinted_correct}/{len(hinted)} 提示后答对",
        )

    # ── 认知诊断维度 ──────────────────────────────────────

    def calc_bkt_convergence(self, result: Dict) -> MetricResult:
        """BKT 收敛速度：掌握度达到稳定所需答题数"""
        mastery_snap = result.get("mastery_trajectory", [])
        if len(mastery_snap) < 5:
            return MetricResult("BKT收敛速度", "认知诊断", "L2", -1, 8, 15, "unknown", "快照不足")

        # 找连续3题波动 < 0.05 的最早位置
        converge_at = -1
        for i in range(len(mastery_snap) - 2):
            diffs = [
                abs(mastery_snap[i] - mastery_snap[i + 1]),
                abs(mastery_snap[i + 1] - mastery_snap[i + 2]),
            ]
            if max(diffs) < 0.05:
                converge_at = i + 2
                break

        if converge_at < 0:
            converge_at = len(mastery_snap)

        return MetricResult(
            name="BKT收敛速度",
            dimension="认知诊断",
            level="L2",
            value=converge_at,
            threshold_good=8,
            threshold_warn=15,
            status="good" if converge_at <= 8 else ("warn" if converge_at <= 15 else "critical"),
            detail=f"在 {converge_at} 题后收敛" if converge_at > 0 else "未收敛",
        )

    def calc_theta_stability(self, result: Dict) -> MetricResult:
        """θ 估计稳定性：单题波动幅度"""
        theta_snap = result.get("theta_trajectory", [])
        if len(theta_snap) < 3:
            return MetricResult("θ估计稳定性", "认知诊断", "L3", -1, 0.3, 0.6, "unknown", "快照不足")

        diffs = [abs(theta_snap[i] - theta_snap[i + 1]) for i in range(len(theta_snap) - 1)]
        max_jump = max(diffs)
        avg_jump = sum(diffs) / len(diffs)

        return MetricResult(
            name="θ估计稳定性",
            dimension="认知诊断",
            level="L3",
            value=round(max_jump, 2),
            threshold_good=0.3,
            threshold_warn=0.6,
            status="good" if max_jump <= 0.3 else ("warn" if max_jump <= 0.6 else "critical"),
            detail=f"最大跳变={max_jump:.2f}, 平均={avg_jump:.2f}",
        )

    def calc_mastery_false_positive(self, result: Dict) -> MetricResult:
        """掌握度假阳性率：精通节点但答错的比例"""
        # 需要答对/答错历史 + 对应 KP 掌握度
        feedbacks = result.get("feedbacks", [])
        if len(feedbacks) < 10:
            return MetricResult("掌握度假阳性", "认知诊断", "L3", -1, 0.1, 0.2, "unknown", "反馈不足")

        # 简化：看反馈中报告的 mastery 高但答错的情况
        false_pos = 0
        total_high_mastery = 0
        for fb in feedbacks:
            mastery = fb.get("avg_mastery", 0)
            is_correct = fb.get("is_correct", True)
            if mastery > 0.85:
                total_high_mastery += 1
                if not is_correct:
                    false_pos += 1

        if total_high_mastery == 0:
            return MetricResult("掌握度假阳性", "认知诊断", "L3", 0, 0.1, 0.2, "good", "无高掌握度样本")

        rate = false_pos / total_high_mastery
        return MetricResult(
            name="掌握度假阳性",
            dimension="认知诊断",
            level="L3",
            value=round(rate, 2),
            threshold_good=0.1,
            threshold_warn=0.2,
            status="good" if rate <= 0.1 else ("warn" if rate <= 0.2 else "critical"),
            detail=f"{false_pos}/{total_high_mastery} 高掌握度答错",
        )

    # ── 用户体验维度 ──────────────────────────────────────

    def _get_feedbacks(self, result: Dict) -> list:
        """从多种可能字段中提取 feedbacks"""
        fbs = result.get("_raw_feedbacks", [])
        if not fbs:
            fbs = result.get("feedbacks", [])
        return fbs

    def calc_completion_rate(self, result: Dict) -> MetricResult:
        """会话完成率：有效产出会话比例"""
        actions = result.get("actions_count", 0)
        feedbacks = result.get("feedbacks_count", 0)

        if actions == 0 and feedbacks == 0:
            actions = len(self._get_actions(result))
            feedbacks = len(self._get_feedbacks(result))

        if actions == 0:
            return MetricResult("会话完成率", "用户体验", "L3", 0, 0.85, 0.7, "critical", "无操作记录")

        rate = feedbacks / actions if actions > 0 else 0
        return MetricResult(
            name="会话完成率",
            dimension="用户体验",
            level="L3",
            value=round(rate, 2),
            threshold_good=0.85,
            threshold_warn=0.7,
            status="good" if rate >= 0.85 else ("warn" if rate >= 0.7 else "critical"),
            detail=f"{feedbacks}/{actions} 反馈/动作",
        )

    # ── 个性化维度 ──────────────────────────────────────

    def calc_mode_switch_reasonableness(self, result: Dict) -> MetricResult:
        """模式切换合理性：切换后正确率变化"""
        feedbacks = self._get_feedbacks(result)
        if len(feedbacks) < 10:
            return MetricResult("模式切换合理性", "个性化", "L2", -1, 0, -0.2, "unknown", f"数据不足({len(feedbacks)}条)")

        # 对比前后半段正确率
        mid = len(feedbacks) // 2
        first_half = sum(1 for f in feedbacks[:mid] if f.get("is_correct")) / max(mid, 1)
        second_half = sum(1 for f in feedbacks[mid:] if f.get("is_correct")) / max(len(feedbacks) - mid, 1)
        delta = second_half - first_half

        return MetricResult(
            name="模式切换合理性",
            dimension="个性化",
            level="L2",
            value=round(delta, 2),
            threshold_good=0,
            threshold_warn=-0.2,
            status="good" if delta >= 0 else ("warn" if delta >= -0.2 else "critical"),
            detail=f"前半={first_half:.0%}, 后半={second_half:.0%}, delta={delta:+.0%}",
        )

    def calc_difficulty_smoothness(self, result: Dict) -> MetricResult:
        """难度递进平滑度：逐题难度变化幅度"""
        recs = self._get_recommendations(result)
        items = self._extract_question_items(recs)
        diffs = [it.get("difficulty") for it in items if it.get("difficulty") is not None]

        if len(diffs) < 4:
            return MetricResult("难度递进平滑度", "个性化", "L3", -1, 1.2, 2.0, "unknown", "推荐数据不足")

        jumps = [abs(diffs[i] - diffs[i + 1]) for i in range(len(diffs) - 1)]
        avg_jump = sum(jumps) / len(jumps)

        # 检测连续递增: 连续4题难度递增
        consecutive_increases = 0
        max_consecutive = 0
        for i in range(1, len(diffs)):
            if diffs[i] > diffs[i - 1]:
                consecutive_increases += 1
                max_consecutive = max(max_consecutive, consecutive_increases)
            else:
                consecutive_increases = 0

        return MetricResult(
            name="难度递进平滑度",
            dimension="个性化",
            level="L3",
            value=round(avg_jump, 2),
            threshold_good=1.2,
            threshold_warn=2.0,
            status="good" if avg_jump <= 1.2 else ("warn" if avg_jump <= 2.0 else "critical"),
            detail=f"平均跳变={avg_jump:.1f}, 最长连续递增={max_consecutive}题",
        )

    # ── 综合计算方法 ──────────────────────────────────────

    def calculate_all(self, verbose: bool = False) -> List[MetricResult]:
        """计算所有可用指标"""
        self.metrics = []

        for result in self.results:
            profile_id = result.get("profile_id", "?")
            traj_id = result.get("trajectory_id", "?")

            calc_methods = [
                self.calc_difficulty_match,
                self.calc_coverage_rate,
                self.calc_hint_effectiveness,
                self.calc_bkt_convergence,
                self.calc_theta_stability,
                self.calc_mastery_false_positive,
                self.calc_completion_rate,
                self.calc_mode_switch_reasonableness,
                self.calc_difficulty_smoothness,
            ]

            for method in calc_methods:
                try:
                    metric = method(result)
                    metric.detail = f"[{profile_id}/{traj_id}] {metric.detail}"
                    self.metrics.append(metric)
                    if verbose:
                        print(f"  {metric.name}: {metric.value} [{metric.status}]")
                except Exception as e:
                    if verbose:
                        print(f"  {method.__name__}: ERROR - {e}")

        return self.metrics

    def summary_by_dimension(self) -> Dict[str, Dict]:
        """按维度汇总"""
        dims = {}
        for m in self.metrics:
            if m.dimension not in dims:
                dims[m.dimension] = {"metrics": [], "good": 0, "warn": 0, "critical": 0, "unknown": 0}
            dims[m.dimension]["metrics"].append(m)
            dims[m.dimension][m.status] += 1

        summary = {}
        for dim, data in dims.items():
            total = len(data["metrics"])
            summary[dim] = {
                "metric_count": total,
                "good_rate": round(data["good"] / max(total, 1), 2),
                "warn_count": data["warn"],
                "critical_count": data["critical"],
                "unknown_count": data["unknown"],
                "health": "healthy" if data["critical"] == 0 and data["warn"] <= 1 else
                          ("warning" if data["critical"] <= 1 else "critical"),
            }
        return summary

    def global_health_score(self) -> float:
        """全局健康分 (0-100)"""
        if not self.metrics:
            return 0
        scores = {"good": 100, "warn": 60, "critical": 20, "unknown": 0}
        total = sum(scores.get(m.status, 0) for m in self.metrics)
        return round(total / len(self.metrics), 1)
