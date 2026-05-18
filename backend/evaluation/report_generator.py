"""
评测报告生成器

输出 Markdown 格式的完整评测报告，包括：
- 概览仪表盘
- 六维度指标详情
- Bad Case 列表
- 改进建议
"""

import os
from datetime import datetime
from typing import Dict, List, Any

from evaluation.metrics_engine import MetricResult
from evaluation.badcase_detector import BadCase


class ReportGenerator:
    """评测报告生成器"""

    def __init__(self, output_dir: str = None):
        self.output_dir = output_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "docs", "evaluation_reports"
        )
        os.makedirs(self.output_dir, exist_ok=True)

    def generate(
        self,
        metrics: List[MetricResult],
        bad_cases: List[BadCase],
        dimension_summary: Dict[str, Dict],
        global_score: float,
        run_metadata: Dict[str, Any] = None,
    ) -> str:
        """生成完整评测报告"""
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M")
        filename = f"eval_report_{now.strftime('%Y%m%d_%H%M%S')}.md"

        lines = [
            f"# AI Tutor 评测报告",
            f"",
            f"**生成时间**: {timestamp}",
            f"**全局健康分**: {global_score}/100",
        ]

        if run_metadata:
            lines.append("")
            lines.append("## 运行概要")
            lines.append("")
            for k, v in run_metadata.items():
                lines.append(f"- **{k}**: {v}")

        # ── 健康仪表盘 ──────────────────────────────────
        lines.extend([
            "",
            "## 一、六维健康仪表盘",
            "",
            "| 维度 | 指标数 | 健康率 | P0 | P1 | P2 | 状态 |",
            "|------|--------|--------|----|----|----|------|",
        ])

        # 统计每个维度的 Bad Case
        dim_cases: Dict[str, Dict[str, int]] = {}
        for bc in bad_cases:
            dim = bc.dimension
            if dim not in dim_cases:
                dim_cases[dim] = {"P0": 0, "P1": 0, "P2": 0}
            dim_cases[dim][bc.severity] += 1

        dimensions_order = ["推荐质量", "教学效果", "认知诊断", "用户体验", "个性化", "鲁棒性"]
        for dim in dimensions_order:
            summary = dimension_summary.get(dim, {})
            bc_counts = dim_cases.get(dim, {})
            health_icon = {
                "healthy": "🟢",
                "warning": "🟡",
                "critical": "🔴",
            }.get(summary.get("health", "healthy"), "⚪")

            lines.append(
                f"| {health_icon} {dim} | {summary.get('metric_count', 0)} | "
                f"{summary.get('good_rate', 0):.0%} | "
                f"{bc_counts.get('P0', 0)} | {bc_counts.get('P1', 0)} | {bc_counts.get('P2', 0)} | "
                f"{summary.get('health', '?')} |"
            )

        # ── 指标详情 ────────────────────────────────────
        lines.extend([
            "",
            "## 二、指标详情",
            "",
        ])

        for dim in dimensions_order:
            dim_metrics = [m for m in metrics if m.dimension == dim]
            if not dim_metrics:
                continue
            lines.extend([
                f"### {dim}",
                "",
                "| 指标 | 值 | 目标 | 状态 | 说明 |",
                "|------|-----|------|------|------|",
            ])
            for m in dim_metrics:
                status_icon = {"good": "✅", "warn": "⚠️", "critical": "❌", "unknown": "⬜"}.get(m.status, "?")
                lines.append(
                    f"| {m.name} ({m.level}) | {m.value} | "
                    f"<{m.threshold_good} | {status_icon} {m.status} | {m.detail} |"
                )
            lines.append("")

        # ── Bad Case 列表 ────────────────────────────────
        lines.extend([
            "## 三、Bad Case 分析",
            "",
        ])

        if not bad_cases:
            lines.append("🎉 本次评测未发现 Bad Case，所有指标在健康范围内。")
        else:
            # 按严重程度排序
            sorted_cases = sorted(bad_cases, key=lambda c: {"P0": 0, "P1": 1, "P2": 2}[c.severity])

            lines.extend([
                f"共发现 **{len(bad_cases)}** 个 Bad Case",
                "",
                "| ID | 严重 | 维度 | 标题 | 指标值 |",
                "|----|------|------|------|--------|",
            ])
            for case in sorted_cases:
                severity_tag = {"P0": "🔴 P0", "P1": "🟡 P1", "P2": "🟢 P2"}.get(case.severity, case.severity)
                lines.append(
                    f"| {case.case_id} | {severity_tag} | {case.dimension} | "
                    f"{case.title} | {case.trigger_metric}={case.trigger_value} |"
                )
            lines.append("")

            # 详细分析（仅 P0 和 P1）
            for case in sorted_cases:
                if case.severity in ("P0", "P1"):
                    lines.append(case.to_markdown())

        # ── 改进建议汇总 ──────────────────────────────────
        lines.extend([
            "## 四、改进建议优先级",
            "",
            "| 优先级 | Bad Case | 建议操作 | 预期效果 |",
            "|--------|----------|---------|---------|",
        ])
        for case in sorted(bad_cases, key=lambda c: {"P0": 0, "P1": 1, "P2": 2}[c.severity]):
            lines.append(
                f"| {case.severity} | {case.title} | {case.suggested_fix.split('；')[0] if case.suggested_fix else '待定'} | "
                f"解决{case.dimension}维度{case.rule_name}问题 |"
            )
        lines.append("")

        # ── 页脚 ────────────────────────────────────────
        lines.extend([
            "---",
            f"*报告由 AI Tutor 评测引擎自动生成 | {timestamp}*",
        ])

        content = "\n".join(lines)

        # 写入文件
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        return content
