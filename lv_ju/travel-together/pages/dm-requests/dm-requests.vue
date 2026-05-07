<template>
  <view class="page">
    <view class="tabs">
      <text class="tab" :class="{ on: tab === 'incoming' }" @click="tab = 'incoming'; load()">收到的</text>
      <text class="tab" :class="{ on: tab === 'outgoing' }" @click="tab = 'outgoing'; load()">发出的</text>
    </view>
    <view v-if="loading" class="hint">加载中…</view>
    <view v-else-if="!items.length" class="hint">暂无待处理申请</view>
    <view v-for="it in items" :key="it.requestId" class="card">
      <view class="card-head">
        <text class="strong">{{ tab === 'incoming' ? it.fromUser.nickname : it.toUser.nickname }}</text>
        <text class="muted">{{ formatChatTime(it.createdAt) }}</text>
      </view>
      <text v-if="it.introText" class="intro">「{{ it.introText }}」</text>
      <text class="act">活动 {{ it.activityId }}</text>
      <view v-if="tab === 'incoming' && it.status === 'pending'" class="actions">
        <button class="btn ok" @click="accept(it)">同意</button>
        <button class="btn no" @click="reject(it)">拒绝</button>
      </view>
      <view v-else-if="tab === 'outgoing' && it.status === 'pending'" class="actions">
        <button class="btn no full" @click="cancelReq(it)">撤回申请</button>
      </view>
      <text v-else class="status">{{ statusLabel(it.status) }}</text>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import {
  acceptDmRequest,
  cancelDmRequest,
  listDmRequests,
  rejectDmRequest,
} from '../../utils/api.js'
import { getToken } from '../../utils/request.js'
import { formatChatTime } from '../../utils/time.js'

const tab = ref('incoming')
const items = ref([])
const loading = ref(false)

function statusLabel(s) {
  const m = { pending: '待处理', accepted: '已同意', rejected: '已拒绝', cancelled: '已撤回' }
  return m[s] || s
}

async function load() {
  if (!getToken()) {
    uni.redirectTo({ url: '/pages/login/login' })
    return
  }
  loading.value = true
  try {
    const data = await listDmRequests(tab.value, 'pending', 1)
    items.value = data.list || []
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function accept(it) {
  try {
    const data = await acceptDmRequest(it.requestId)
    uni.showToast({ title: '已同意', icon: 'success' })
    uni.navigateTo({
      url:
        '/pages/direct-chat-detail/direct-chat-detail?threadId=' +
        encodeURIComponent(data.threadId) +
        '&peerNickname=' +
        encodeURIComponent(it.fromUser.nickname),
    })
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  }
}

async function reject(it) {
  try {
    await rejectDmRequest(it.requestId)
    uni.showToast({ title: '已拒绝', icon: 'none' })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  }
}

async function cancelReq(it) {
  try {
    await cancelDmRequest(it.requestId)
    uni.showToast({ title: '已撤回', icon: 'none' })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '失败', icon: 'none' })
  }
}

onShow(() => {
  load()
})
</script>

<style scoped>
.page {
  min-height: 100vh;
  padding-bottom: 48rpx;
}
.tabs {
  display: flex;
  background: #fff;
  border-bottom: 1rpx solid #eee;
}
.tab {
  flex: 1;
  text-align: center;
  padding: 28rpx 0;
  font-size: 30rpx;
  color: #666;
}
.tab.on {
  color: #007aff;
  font-weight: 600;
  border-bottom: 4rpx solid #007aff;
}
.hint {
  text-align: center;
  color: #999;
  padding: 48rpx;
}
.card {
  margin: 24rpx;
  padding: 28rpx;
  background: #fff;
  border-radius: 16rpx;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.strong {
  font-size: 32rpx;
  font-weight: 600;
}
.muted {
  font-size: 22rpx;
  color: #999;
}
.intro {
  display: block;
  margin-top: 16rpx;
  font-size: 28rpx;
  color: #444;
}
.act {
  display: block;
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #888;
}
.actions {
  display: flex;
  gap: 24rpx;
  margin-top: 24rpx;
}
.btn {
  flex: 1;
  font-size: 28rpx;
  border-radius: 12rpx;
  padding: 16rpx 0;
}
.ok {
  background: #007aff;
  color: #fff;
}
.no {
  background: #f2f2f2;
  color: #333;
}
.no.full {
  flex: none;
  width: 100%;
}
.status {
  margin-top: 16rpx;
  font-size: 26rpx;
  color: #888;
}
</style>
