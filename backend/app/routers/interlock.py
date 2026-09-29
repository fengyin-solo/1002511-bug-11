"""联锁管理接口：维护联锁道岔，覆盖登记异常、安排维修、办理停用等动作。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.schemas import ActionResult, EntryPayload, PageResult
from app.services.interlock import InterlockService


class ActionPayload(BaseModel):
    """动作请求：兼容 {values: {action}} 与页面直接提交 {action} 两种形态。"""

    values: dict[str, Any] = {}
    action: str | None = None

router = APIRouter(prefix="/api/interlock", tags=["联锁管理"])

service = InterlockService()

LIST_FIELDS = ["道岔编号", "所属车站", "道岔类型", "联锁关系", "锁闭方式", "动作次数", "检修周期", "道岔状态"]
STATUSES = ["正常", "动作异常", "维修中", "已停用"]


@router.get("", response_model=PageResult[dict])
def list_entries(
    keyword: str | None = Query(default=None, description="按道岔编号检索"),
    status: str | None = Query(default=None, description="正常、动作异常、维修中、已停用"),
    page: int = 1,
    size: int = 20,
) -> PageResult[dict]:
    """按道岔编号与状态过滤联锁管理列表；没有数据时返回空页，不报错。"""
    if size > 200:
        raise HTTPException(status_code=400, detail="每页最多 200 条，请缩小分页范围")
    items, total = service.list_entries(keyword=keyword, status=status, page=page, size=size)
    return PageResult(items=items, total=total, page=page, size=size)


@router.get("/export")
def export_entries() -> dict[str, Any]:
    """导出联锁管理清单：返回当前过滤条件下的全量数据。"""
    items, total = service.list_entries(page=1, size=10000)
    return {"module": "interlock", "total": total, "items": items}


@router.get("/{entry_id}", response_model=dict)
def get_entry(entry_id: int) -> dict:
    """读取单条联锁道岔明细；不存在时给出可读的错误说明。"""
    entry = service.get_entry(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"联锁道岔 {entry_id} 不存在或已归档")
    return entry


@router.post("", response_model=ActionResult)
def create_entry(payload: EntryPayload) -> ActionResult:
    """登记一条联锁道岔，缺字段时说明原因而不是静默丢弃。"""
    entry, missing = service.create_entry(payload.values)
    if missing:
        return ActionResult(ok=False, message=f"缺少必填字段：{'、'.join(missing)}")
    return ActionResult(ok=True, message="联锁道岔已登记", entry=entry)


@router.post("/{entry_id}/actions", response_model=ActionResult)
def run_action(entry_id: int, payload: ActionPayload) -> ActionResult:
    """对单条联锁道岔执行登记异常、安排维修、办理停用；不允许的动作会被拦下并说明原因。"""
    action = str(payload.action or payload.values.get("action") or "").strip()
    entry, message = service.run_action(entry_id, action)
    if entry is None:
        return ActionResult(ok=False, message=message)
    return ActionResult(ok=True, message=message, entry=entry)
