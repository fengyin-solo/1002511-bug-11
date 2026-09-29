"""联锁管理业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "interlock"
REQUIRED_FIELDS = ["道岔编号", "所属车站", "道岔类型"]
STATUS_ORDER = ["正常", "动作异常", "维修中", "已停用"]
ACTION_RULES = {"登记异常": "动作异常", "安排维修": "维修中", "办理停用": "已停用"}
# 只有“登记异常”会把道岔打上异常标记；安排维修、办理停用都要把异常标记清掉。
NEGATIVE_ACTIONS = ["登记异常"]
STATUS_FIELD = "道岔状态"
COUNTER_FIELD = "动作次数"
DISABLED_STATUS = "已停用"


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
        entry[STATUS_FIELD] = STATUS_ORDER[0]
        entry[COUNTER_FIELD] = 0
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"联锁道岔 {entry_id} 不存在或已归档，状态保持不变"
        code = str(entry.get("道岔编号") or "").strip()
        if not code:
            return None, f"联锁道岔 {entry_id} 缺少道岔编号，无法办理动作，状态保持不变"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于联锁管理可执行范围，状态保持不变"

        current = entry.get("status")
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里，状态保持不变"

        # 已停用是终态：不允许再安排维修，也不允许重复停用。
        if current == DISABLED_STATUS:
            return None, f"道岔 {code} 已办理停用，不能再{action}，状态保持不变"
        # 同一台道岔重复提交同一次登记异常只生效一次，且不重复累计动作次数。
        if action == "登记异常" and current == target:
            return None, f"道岔 {code} 已登记过动作异常，无需重复登记，状态保持不变"

        entry["status"] = target
        # 列表展示用的“道岔状态”与内部 status 必须保持同一口径，列表与详情才不会打架。
        entry[STATUS_FIELD] = target
        entry[COUNTER_FIELD] = self._read_counter(entry) + 1
        entry["pending"] = target != DISABLED_STATUS
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"道岔 {code} 已{action}，当前状态：{target}"

    @staticmethod
    def _read_counter(entry: dict[str, Any]) -> int:
        """动作次数历史数据可能是文本，解析不了就从 0 重新累计，保证计数始终可更新。"""
        raw = entry.get(COUNTER_FIELD)
        if isinstance(raw, (int, float)):
            return int(raw)
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            return 0
