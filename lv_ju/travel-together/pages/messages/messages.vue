<template>
  <view class="page">
    <view class="toolbar">
      <button class="link" @click="goDmRequests">私聊申请</button>
    </view>
    <view v-if="!rows.length && !loading" class="empty">暂无会话</view>
    <view
      v-for="item in rows"
      :key="item.key"
      class="cell"
      @click="openRow(item)"
    >
      <view class="badge">{{ item.kind === 'activity' ? '群' : '私' }}</view>
      <view class="main">
        <view class="title-row">
          <text class="title">{{ item.title }}</text>
          <text class="time">{{ formatChatTime(item.time) }}</text>
        </view>
        <view class="sub-row">
          <text class="sub">{{ item.subtitle || ' ' }}</text>
          <view v-if="item.unread > 0" class="dot">{{ item.unread > 99 ? '99+' : item.unread }}</view>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { getDirectChats, getMyChats } from '../../utils/api.js'
import { getToken } from '../../utils/request.js'
import { formatChatTime } from '../../utils/time.js'

const rows = ref([])
const loading = ref(false)

function mergeRows(chats, directs) {
  const list = []
  for (const c of chats.list || []) {
    list.push({
      kind: 'activity',
      key: `a-${c.activityId}`,
      title: c.title,
      subtitle: c.lastMessage,
      time: c.lastMessageAt,
      sortAt: c.lastMessageAt ? new Date(c.lastMessageAt).getTime() : 0,
      activityId: c.activityId,
      unread: c.unreadCount || 0,
    })
  }
  for (const d of directs.list || []) {
    list.push({
      kind: 'direct',
      key: `d-${d.threadId}`,
      title: d.peerNickname,
      subtitle: d.lastMessage,
      time: d.lastMessageAt,
      sortAt: d.lastMessageAt ? new Date(d.lastMessageAt).getTime() : 0,
      threadId: d.threadId,
      peerUserId: d.peerUserId,
      peerNickname: d.peerNickname,
      unread: d.unreadCount || 0,
    })
  }
  list.sort((a, b) => b.sortAt - a.sortAt)
  return list
}

async function load() {
  if (!getToken()) {
    uni.redirectTo({ url: '/pages/login/login' })
    return
  }
  loading.value = true
  try {
    const [chats, directs] = await Promise.all([
      getMyChats(1, 50),
      getDirectChats(1, 50),
    ])
    rows.value = mergeRows(chats, directs)
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openRow(item) {
  if (item.kind === 'activity') {
    uni.navigateTo({
      url: `/pages/chat-detail/chat-detail?activityId=${encodeURIComponent(item.activityId)}`,
    })
  } else {
    const q = `threadId=${encodeURIComponent(item.threadId)}&peerNickname=${encodeURIComponent(item.peerNickname || '')}`
    uni.navigateTo({ url: `/pages/direct-chat-detail/direct-chat-detail?${q}` })
  }
}

function goDmRequests() {
  uni.navigateTo({ url: '/pages/dm-requests/dm-requests' })
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
.toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 16rpx 24rpx;
}
.link {
  font-size: 28rpx;
  color: #007aff;
  background: transparent;
  border: none;
}
.link::after {
  border: none;
}
.empty {
  text-align: center;
  color: #999;
  padding: 120rpx 0;
}
.cell {
  display: flex;
  align-items: flex-start;
  padding: 24rpx 32rpx;
  background: #fff;
  border-bottom: 1rpx solid #eee;
}
.badge {
  width: 56rpx;
  height: 56rpx;
  line-height: 56rpx;
  text-align: center;
  border-radius: 12rpx;
  background: #eef6ff;
  color: #007aff;
  font-size: 24rpx;
  margin-right: 20rpx;
  flex-shrink: 0;
}
.main {
  flex: 1;
  min-width: 0;
}
.title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16rpx;
}
.title {
  font-size: 32rpx;
  font-weight: 600;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.time {
  font-size: 22rpx;
  color: #999;
  flex-shrink: 0;
}
.sub-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8rpx;
}
.sub {
  font-size: 26rpx;
  color: #888;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dot {
  min-width: 36rpx;
  padding: 0 10rpx;
  height: 36rpx;
  line-height: 36rpx;
  border-radius: 18rpx;
  background: #ff3b30;
  color: #fff;
  font-size: 22rpx;
  text-align: center;
  margin-left: 12rpx;
}
</style>
