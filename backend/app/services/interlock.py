"""联锁管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "interlock"
REQUIRED_FIELDS = ["道岔编号", "所属车站", "道岔类型"]
STATUS_ORDER = ["正常", "动作异常", "维修中", "已停用"]
STATUS_DISABLED = "已停用"
STATUS_ABNORMAL = "动作异常"
STATUS_REPAIRING = "维修中"
ACTION_RULES = {"登记异常": "动作异常", "安排维修": "维修中", "办理停用": "已停用"}
COUNT_FIELD = "动作次数"
DISPLAY_STATUS_FIELD = "道岔状态"


class InterlockService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("道岔编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        entry[COUNT_FIELD] = 0
        # 展示用的「道岔状态」与内部 status 始终保持同一份口径
        entry[DISPLAY_STATUS_FIELD] = entry["status"]
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"联锁道岔 {entry_id} 不存在或已归档"
        point_no = str(entry.get("道岔编号") or "").strip()
        if not point_no:
            return None, "道岔编号缺失，无法办理该动作，状态保持不变"
        if not action:
            return None, "未收到要执行的动作，请重新选择后再提交"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于联锁管理可执行范围"

        current = str(entry.get("status") or "")
        target = ACTION_RULES[action]

        # 状态前置校验：拦截不允许的流转，原状态、动作次数、异常标记都保持不变
        if action == "安排维修" and current == STATUS_DISABLED:
            return None, f"道岔 {point_no} 已办理停用，不能再安排维修"
        if action == "登记异常" and current == STATUS_ABNORMAL:
            return None, f"道岔 {point_no} 已登记异常，请勿重复提交"

        entry["status"] = target
        # 维修中、已停用都不再占用待处理；正常、动作异常仍待跟进
        entry["pending"] = target not in (STATUS_REPAIRING, STATUS_DISABLED)
        # 只有动作异常挂异常标记；安排维修后异常随维修流程解除
        entry["abnormal"] = target == STATUS_ABNORMAL
        entry[COUNT_FIELD] = self._next_count(entry.get(COUNT_FIELD))
        # 列表展示字段与内部 status 同步，列表页与详情页读到同一份状态
        entry[DISPLAY_STATUS_FIELD] = target
        return entry, f"道岔 {point_no} 已{action}"

    @staticmethod
    def _next_count(value: Any) -> int:
        try:
            return int(value) + 1
        except (TypeError, ValueError):
            # 历史脏数据（如占位文字）不参与计数，从 1 开始重新累计
            return 1
