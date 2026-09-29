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
          <th>异常标记</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayValue(row, column) }}</td>
          <td>{{ row.abnormal ? '异常' : '正常' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!canRunAction(action, row)"
              :title="actionHint(action, row)"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 2" class="empty-state">暂无联锁管理数据，可先登记联锁道岔</td>
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

type Row = Record<string, string | number | boolean | null>

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

// 已停用是终态，任何流转动作都不能再点；登记异常也不允许对同一台道岔重复提交。
function canRunAction(action: string, row: Row): boolean {
  const status = String(row.status ?? '')
  if (status === '已停用') {
    return false
  }
  if (action === '登记异常' && status === '动作异常') {
    return false
  }
  return true
}

function actionHint(action: string, row: Row): string {
  const status = String(row.status ?? '')
  if (status === '已停用') {
    return '道岔已办理停用，不能再执行任何流转动作'
  }
  if (action === '登记异常' && status === '动作异常') {
    return '该道岔已登记过动作异常，无需重复登记'
  }
  return action
}

function displayValue(row: Row, column: string): string | number {
  const value = row[column]
  return value === null || value === undefined || value === '' ? '—' : (value as string | number)
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
  const code = String(row['道岔编号'] ?? '').trim()
  if (!code) {
    errorMessage.value = '该记录缺少道岔编号，无法办理动作，状态保持不变'
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
    const payload = await response.json()
    // 后端业务失败时 HTTP 仍是 200，以 ok 字段为准并展示原因；不做本地改动，列表保持原状态。
    if (!payload.ok) {
      errorMessage.value = payload.message || '联锁管理动作未生效，状态保持不变'
      return
    }
    errorMessage.value = payload.message || ''
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '联锁管理操作失败，状态保持不变'
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
