<template>
  <section class="page" data-module="interlock">
    <header class="page-head">
      <div>
        <h2>联锁管理管理</h2>
        <p class="page-desc">维护联锁道岔，围绕道岔编号、所属车站、道岔类型、联锁关系做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记联锁道岔</button>
        <button class="btn" type="button" @click="exportRows">导出联锁管理清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!actionAllowed(action, row)"
              :title="actionAllowed(action, row) ? '' : actionBlockedReason(action, row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无联锁管理数据，可先登记联锁道岔</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条联锁管理记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface ActionResponse {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/interlock'
const columns = ["道岔编号", "所属车站", "道岔类型", "联锁关系", "锁闭方式", "动作次数", "检修周期", "道岔状态"]
const actions = ["登记异常", "安排维修", "办理停用"]
const statuses = ["正常", "动作异常", "维修中", "已停用"]
const stats = [{"label": "正常道岔", "value": 0}, {"label": "异常道岔", "value": 0}, {"label": "维修中道岔", "value": 0}]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

function rowStatus(row: Row): string {
  return String(row['道岔状态'] ?? row.status ?? '')
}

function actionBlockedReason(action: string, row: Row): string {
  const status = rowStatus(row)
  if (action === '安排维修' && status === '已停用') {
    return '已办理停用的道岔不能再安排维修'
  }
  if (action === '登记异常' && status === '动作异常') {
    return '该道岔已登记异常，请勿重复提交'
  }
  return ''
}

function actionAllowed(action: string, row: Row): boolean {
  return actionBlockedReason(action, row) === ''
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '联锁道岔登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  if (!row.id) {
    errorMessage.value = '该道岔缺少编号，无法执行动作，状态保持不变'
    return
  }
  const blocked = actionBlockedReason(action, row)
  if (blocked) {
    errorMessage.value = blocked
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('联锁管理动作未生效，请稍后重试')
    }
    const result = (await response.json()) as ActionResponse
    if (!result.ok) {
      // 业务规则拦下（如停用后再维修、重复登记异常）：原状态不动，说明原因
      errorMessage.value = result.message
      return
    }
    // 成功后用后端返回的最新记录刷新当前行，并重新拉取列表，保证列表与详情一致
    if (result.entry) {
      Object.assign(row, result.entry)
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '联锁管理操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('联锁道岔列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '联锁管理列表读取失败'
  }
}

onMounted(reload)
</script>
