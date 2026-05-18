"""
答题模拟器 — 通过真实 API 或数据库直接注入模拟用户答题

两种模式：
- live:  通过 HTTP API 调用 (需要后台运行中)
- replay: 直接写入数据库 + Redis (离线批量评测)
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

import httpx

# 添加 backend 到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.profiles import PROFILES, UserProfile
from evaluation.trajectories import TRAJECTORIES, TrajectoryGenerator, AnswerAction

BASE_URL = os.getenv("EVAL_BASE_URL", "http://localhost:8000")


@dataclass
class SimulationResult:
    """单次模拟的运行结果"""
    profile_id: str
    trajectory_id: str
    user_id: int
    username: str
    access_token: str
    actions: List[AnswerAction] = field(default_factory=list)
    recommendations: List[Dict] = field(default_factory=list)
    feedbacks: List[Dict] = field(default_factory=list)
    theta_snapshots: List[float] = field(default_factory=list)
    mastery_snapshots: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_time_ms: float = 0

    def to_dict(self) -> dict:
        return {
            "profile_id": self.profile_id,
            "trajectory_id": self.trajectory_id,
            "user_id": self.user_id,
            "actions_count": len(self.actions),
            "recommendations_count": len(self.recommendations),
            "feedbacks_count": len(self.feedbacks),
            "theta_trajectory": self.theta_snapshots,
            "mastery_trajectory": self.mastery_snapshots,
            "error_count": len(self.errors),
            "errors": self.errors[-5:],  # 只保留最后5条
            "total_time_ms": self.total_time_ms,
        }


class APISimulator:
    """通过 HTTP API 进行模拟 (Live 模式)"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0, base_url=base_url)

    async def close(self):
        await self.client.aclose()

    async def register_user(self, profile: UserProfile, traj_id: str) -> SimulationResult:
        """注册测试用户"""
        username = f"eval_{profile.id}_{traj_id}_{int(time.time())}"
        resp = await self.client.post("/auth/register", json={
            "username": username,
            "password": "evaltest123",
            "email": f"{username}@eval.test",
        })
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"注册失败: {resp.status_code} {resp.text}")

        data = resp.json()
        return SimulationResult(
            profile_id=profile.id,
            trajectory_id=traj_id,
            user_id=data["id"],
            username=username,
            access_token="",  # 注册后需登录
        )

    async def login(self, result: SimulationResult) -> SimulationResult:
        """登录获取 token"""
        resp = await self.client.post("/auth/login", json={
            "username": result.username,
            "password": "evaltest123",
        })
        if resp.status_code != 200:
            result.errors.append(f"登录失败: {resp.status_code}")
            return result

        data = resp.json()
        result.access_token = data["access_token"]
        return result

    def _auth_headers(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    async def init_profile(self, result: SimulationResult) -> SimulationResult:
        """初始化用户画像"""
        resp = await self.client.get(
            "/advisor/init",
            headers=self._auth_headers(result.access_token),
        )
        if resp.status_code != 200:
            result.errors.append(f"画像初始化失败: {resp.status_code}")
        return result

    async def get_recommendation(self, result: SimulationResult, limit: int = 5) -> Optional[Dict]:
        """获取推荐题目"""
        resp = await self.client.get(
            "/advisor/recommend",
            params={"limit": limit},
            headers=self._auth_headers(result.access_token),
        )
        if resp.status_code != 200:
            result.errors.append(f"推荐失败: {resp.status_code}")
            return None
        data = resp.json()
        return data.get("data", {})

    async def submit_feedback(
        self, result: SimulationResult, question_id: int, action: AnswerAction
    ) -> Optional[Dict]:
        """提交答题反馈"""
        resp = await self.client.post(
            "/advisor/feedback",
            json={
                "question_id": question_id,
                "is_correct": action.is_correct,
                "hint_count": action.hint_count,
                "time_spent": action.time_spent,
                "skip_reason": action.skip_reason,
                "algorithm_version": "advisor-v1",
            },
            headers=self._auth_headers(result.access_token),
        )
        if resp.status_code != 200:
            result.errors.append(f"反馈失败(q={question_id}): {resp.status_code}")
            return None
        return resp.json().get("data", {})

    async def get_profile_snapshot(self, result: SimulationResult) -> Optional[Dict]:
        """获取画像快照"""
        resp = await self.client.get(
            "/advisor/profile",
            headers=self._auth_headers(result.access_token),
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("data", {})

    async def run_trajectory(
        self,
        profile: UserProfile,
        trajectory_id: str,
        trajectory_type: str,
        n_questions: int = 30,
    ) -> SimulationResult:
        """运行一条完整的答题轨迹"""
        t0 = time.time()

        # 1. 注册 + 登录 + 初始化
        result = await self.register_user(profile, trajectory_id)
        result = await self.login(result)
        if not result.access_token:
            result.total_time_ms = (time.time() - t0) * 1000
            return result

        result = await self.init_profile(result)

        # 2. 生成答题动作序列
        generator = TrajectoryGenerator(profile, seed=hash(f"{profile.id}_{trajectory_id}") % 10000)
        # 用随机难度序列模拟推荐结果
        difficulties = [(i % 5) + 1 for i in range(n_questions)]  # 1-5 难度均匀分布
        actions = generator.generate(trajectory_type, difficulties)
        result.actions = actions

        # 3. 逐题：获取推荐 → 模拟答题 → 提交反馈
        for i, action in enumerate(actions):
            # 获取推荐
            rec = await self.get_recommendation(result)
            if rec:
                result.recommendations.append(rec)
                # 取第一道推荐题
                questions = rec.get("questions", [])
                if questions:
                    q = questions[0]
                    q_id = q.get("question_id") or q.get("id")
                    if q_id:
                        # 提交反馈
                        fb = await self.submit_feedback(result, int(q_id), action)
                        if fb:
                            result.feedbacks.append(fb)
                            # 记录 theta 和 mastery 快照
                            theta = fb.get("theta") or fb.get("theta_estimate")
                            if theta is not None:
                                result.theta_snapshots.append(float(theta))
                            mastery = fb.get("avg_mastery")
                            if mastery is not None:
                                result.mastery_snapshots.append(float(mastery))

            # 每 5 题获取一次画像快照
            if i % 5 == 4:
                snapshot = await self.get_profile_snapshot(result)
                if snapshot and not result.theta_snapshots:
                    result.theta_snapshots.append(float(snapshot.get("theta", 0)))

        result.total_time_ms = (time.time() - t0) * 1000
        return result


async def run_all_simulations(
    base_url: str = BASE_URL,
    profiles: List[str] = None,
    trajectories: List[str] = None,
    n_questions: int = 30,
) -> List[SimulationResult]:
    """运行全部模拟评测"""
    if profiles is None:
        profiles = list(PROFILES.keys())
    if trajectories is None:
        trajectories = list(TRAJECTORIES.keys())

    sim = APISimulator(base_url)
    results = []

    try:
        for pid in profiles:
            profile = PROFILES[pid]
            for tid in trajectories:
                traj = TRAJECTORIES[tid]
                print(f"  [{pid}] {profile.name} × {traj['name']} ... ", end="", flush=True)
                result = await sim.run_trajectory(
                    profile, tid, traj["type"], n_questions
                )
                status = "OK" if not result.errors else f"{len(result.errors)} errors"
                print(f"{status} ({result.total_time_ms:.0f}ms)")
                results.append(result)
    finally:
        await sim.close()

    return results


if __name__ == "__main__":
    results = asyncio.run(run_all_simulations(
        profiles=["P1", "P3"],  # 快速测试只跑2个画像
        trajectories=["T1", "T2"],
        n_questions=10,
    ))
    for r in results:
        print(json.dumps(r.to_dict(), indent=2, ensure_ascii=False))
