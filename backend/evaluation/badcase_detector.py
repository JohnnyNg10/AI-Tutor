"""
Bad Case 自动发现引擎

基于阈值规则自动扫描指标，发现并分类 Bad Case。
每一条规则对应一个可复现的产品缺陷模式。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

from evaluation.metrics_engine import MetricResult


@dataclass
class BadCase:
    """Bad Case 记录"""
    case_id: str
    title: str
    rule_name: str
    severity: str            # P0 / P1 / P2
    dimension: str
    profile_id: str
    trajectory_id: str
    trigger_metric: str
    trigger_value: float
    trigger_threshold: float
    phenomenon: str
    root_cause_hints: List[str] = field(default_factory=list)
    affected_user_types: List[str] = field(default_factory=list)
    suggested_fix: str = ""
    detected_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_markdown(self) -> str:
        lines = [
            f"## Case #{self.case_id}: {self.title}",
            "",
            f"**发现时间**: {self.detected_at}",
            f"**触发规则**: {self.rule_name}",
            f"**严重程度**: {self.severity}",
            f"**影响维度**: {self.dimension}",
            f"**影响用户**: {self.affected_user_types}",
            "",
            "### 现象",
            self.phenomenon,
            "",
            "### 根因假设",
        ]
        for hint in self.root_cause_hints:
            lines.append(f"- {hint}")
        lines.extend([
            "",
            "### 建议修复",
            self.suggested_fix if self.suggested_fix else "待人工分析",
            "",
            "---",
        ])
        return "\n".join(lines)


# ── Bad Case 检测规则 ──────────────────────────────────────

BADCASE_RULES = [
    {
        "name": "推荐-难度失配",
        "rule": "difficulty_mismatch_chain",
        "dimension": "推荐质量",
        "severity": "P1",
        "check": lambda m: m.name == "难度匹配度" and m.value > 1.5,
        "phenomenon": "推荐题目难度与用户能力持续偏差 > 1.5，存在推题过难或过易的系统性问题。",
        "root_causes": [
            "数据层: 题目 difficulty 标注不准确",
            "算法层: IRT θ 估计滞后于真实能力变化",
            "算法层: ChromaDB 语义召回返回的候选池难度分布不均",
        ],
        "affected": ["P1-数列新手", "P2-基础薄弱"],
        "fix": "短期: 手动检查标注偏差的题目；中期: 引入难度校准定时任务，对比实际正确率与预期正确率",
    },
    {
        "name": "教学-提示失效",
        "rule": "hint_ineffective_chain",
        "dimension": "教学效果",
        "severity": "P0",
        "check": lambda m: m.name == "提示有效率" and 0 <= m.value < 0.35,
        "phenomenon": "学生查看提示后答对率 < 35%，说明提示内容未有效传递解题思路，学生看了提示仍然不会做。",
        "root_causes": [
            "模型层: LLM 生成的提示与题目实际解法不匹配",
            "产品层: L3/L4 提示包含了太多信息但学生无法消化",
            "数据层: RAG 检索到的相似例题与当前题差异过大",
        ],
        "affected": ["P2-基础薄弱", "P3-中等水平"],
        "fix": "短期: 抽查提示内容与题目匹配度；中期: 引入提示质量 LLM-as-Judge 评估；长期: 建立提示模板库",
    },
    {
        "name": "诊断-虚假精通",
        "rule": "mastery_false_positive",
        "dimension": "认知诊断",
        "severity": "P1",
        "check": lambda m: m.name == "掌握度假阳性" and m.value > 0.2,
        "phenomenon": "系统标记为'精通'的知识点，实际答错率 > 20%。学生以为掌握了但实际没有。",
        "root_causes": [
            "算法层: BKT 掌握度阈值 0.85 过于宽松",
            "算法层: Actual Score 中的提示权重过高，学生用提示答对被误判为掌握",
            "产品层: 缺少知识点的间隔检验机制（隔天再测）",
        ],
        "affected": ["P3-中等水平", "P4-进阶高手"],
        "fix": "短期: 将精通阈值从 0.85 提升至 0.90；中期: 引入间隔重测机制，精通需经两次不同时间确认",
    },
    {
        "name": "诊断-收敛过慢",
        "rule": "bkt_slow_convergence",
        "dimension": "认知诊断",
        "severity": "P2",
        "check": lambda m: m.name == "BKT收敛速度" and m.value > 15,
        "phenomenon": "BKT 掌握度在 15 题后仍不稳定，导致冷启动阶段推荐质量差，新用户体验不佳。",
        "root_causes": [
            "算法层: P(T)=0.3 学习率偏低，每次更新幅度小",
            "算法层: 初始 P(L0)=0.5 与真实掌握度差距大",
            "数据层: 前几题答题记录波动大，BKT 更新方向摇摆",
        ],
        "affected": ["P1-数列新手", "P2-基础薄弱"],
        "fix": "短期: 新用户前 5 题使用 P(T)=0.5 加速收敛；中期: 引入分层初始化 P(L0) 基于入学测试",
    },
    {
        "name": "体验-反馈丢失",
        "rule": "low_completion_rate",
        "dimension": "用户体验",
        "severity": "P1",
        "check": lambda m: m.name == "会话完成率" and 0 <= m.value < 0.7,
        "phenomenon": "用户提交的反馈数远少于预期操作数，存在接口丢数据或前端未正确上报的情况。",
        "root_causes": [
            "交互层: analytics.js 的 beforeunload 事件未在所有浏览器触发",
            "交互层: API 返回 500 后未重试即丢弃",
            "数据层: Redis 队列溢出导致事件丢失",
        ],
        "affected": ["全部画像"],
        "fix": "短期: 检查 API 错误日志定位失败原因；中期: 增加提交失败后的本地重试队列",
    },
    {
        "name": "个性化-切换失误",
        "rule": "mode_switch_degradation",
        "dimension": "个性化",
        "severity": "P0",
        "check": lambda m: m.name == "模式切换合理性" and m.value < -0.2,
        "phenomenon": "Advisor 模式切换后学生正确率下降 > 20%，说明切换到了不合适的学习模式。",
        "root_causes": [
            "策略层: SCAFFOLD→ENCOURAGE 切换时机过早",
            "策略层: 软标签联合判定权重不合理，自主性低但被 mastery 高掩盖",
            "算法层: θ 估计波动导致模式频繁切换",
        ],
        "affected": ["P2-基础薄弱", "P3-中等水平"],
        "fix": "短期: 增加模式切换的'冷静期'(至少5题后才能再次切换)；中期: 调整联合判定权重",
    },
    {
        "name": "个性化-难度过山车",
        "rule": "difficulty_rollercoaster",
        "dimension": "个性化",
        "severity": "P2",
        "check": lambda m: m.name == "难度递进平滑度" and m.value > 2.0,
        "phenomenon": "推荐难度逐题跳变过大(>2级)，学生感受到过山车式的学习体验，影响学习信心。",
        "root_causes": [
            "算法层: 推荐排序中 exploration 权重过高，偶发极端难度题目",
            "策略层: 复习题(低难度)与新题(高难度)交替导致跳跃",
            "数据层: 题库难度分布不均，某些难度区间缺少题目",
        ],
        "affected": ["P2-基础薄弱", "P3-中等水平"],
        "fix": "短期: 推荐结果增加难度平滑后处理(限制相邻题目难度差≤2)；中期: 补充中等难度题库",
    },
    {
        "name": "系统-θ剧烈跳变",
        "rule": "theta_volatility",
        "dimension": "认知诊断",
        "severity": "P2",
        "check": lambda m: m.name == "θ估计稳定性" and m.value > 0.6,
        "phenomenon": "单次答题导致 θ 变化 > 0.6，能力估计不稳定，导致推荐质量波动。",
        "root_causes": [
            "算法层: IRT 更新步长未做正则化",
            "数据层: 个别极端答题行为(1秒答对/10次重试)拉偏估计",
            "算法层: K-IRT 联合估算中 new_user 权重切换过于剧烈",
        ],
        "affected": ["全部画像"],
        "fix": "短期: θ 更新增加变化上限 0.5；中期: 引入 EMA 平滑",
    },
]


class BadCaseDetector:
    """Bad Case 自动检测器"""

    def __init__(self):
        self.rules = BADCASE_RULES
        self.cases: List[BadCase] = []
        self._case_counter = 0

    def scan(self, metrics: List[MetricResult], profile_id: str = "", trajectory_id: str = "") -> List[BadCase]:
        """扫描指标列表，发现 Bad Case"""
        new_cases = []

        for metric in metrics:
            for rule in self.rules:
                try:
                    if rule["check"](metric):
                        self._case_counter += 1
                        case = BadCase(
                            case_id=f"BC-{self._case_counter:04d}",
                            title=rule["name"],
                            rule_name=rule["rule"],
                            severity=rule["severity"],
                            dimension=rule["dimension"],
                            profile_id=profile_id,
                            trajectory_id=trajectory_id,
                            trigger_metric=metric.name,
                            trigger_value=metric.value,
                            trigger_threshold=metric.threshold_warn,
                            phenomenon=rule["phenomenon"].format(
                                value=metric.value, threshold=metric.threshold_warn
                            ),
                            root_cause_hints=rule["root_causes"].copy(),
                            affected_user_types=rule["affected"].copy(),
                            suggested_fix=rule["fix"],
                        )
                        new_cases.append(case)
                        self.cases.append(case)
                except Exception:
                    pass

        return new_cases

    def scan_all(self, metrics_by_result: Dict[str, List[MetricResult]]) -> List[BadCase]:
        """批量扫描所有结果的指标"""
        all_cases = []
        for key, metrics in metrics_by_result.items():
            parts = key.split("/")
            pid = parts[0] if parts else ""
            tid = parts[1] if len(parts) > 1 else ""
            cases = self.scan(metrics, pid, tid)
            all_cases.extend(cases)
        return all_cases

    def summary(self) -> Dict[str, Any]:
        """Bad Case 汇总统计"""
        by_severity = {"P0": 0, "P1": 0, "P2": 0}
        by_dimension = {}
        for case in self.cases:
            by_severity[case.severity] = by_severity.get(case.severity, 0) + 1
            by_dimension[case.dimension] = by_dimension.get(case.dimension, 0) + 1

        return {
            "total_cases": len(self.cases),
            "by_severity": by_severity,
            "by_dimension": by_dimension,
            "p0_count": by_severity.get("P0", 0),
            "p1_count": by_severity.get("P1", 0),
            "p2_count": by_severity.get("P2", 0),
            "needs_immediate_action": by_severity.get("P0", 0) > 0,
        }

    def clear(self):
        self.cases = []
        self._case_counter = 0
