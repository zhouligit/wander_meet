<template>
  <view class="page">
    <scroll-view class="scroll" scroll-y :scroll-into-view="scrollInto" @scrolltoupper="onScrollUpper">
      <view v-if="loading && !messages.length" class="hint">加载中…</view>
      <view v-for="m in messages" :id="'dm-' + m.messageId" :key="m.messageId" class="row">
        <view class="bubble-wrap" :class="{ me: m.sender.userId === myUserId }">
          <view class="avatar-sm">{{ m.sender.nickname.slice(0, 1) }}</view>
          <view class="bubble" :class="{ me: m.sender.userId === myUserId }">
            <text v-if="m.msgType === 'text'" class="text">{{ m.text }}</text>
            <image v-else class="img" :src="m.imageUrl" mode="widthFix" />
            <text class="time">{{ formatChatTime(m.createdAt) }}</text>
          </view>
        </view>
      </view>
    </scroll-view>
    <view class="composer">
      <input
        v-model="draft"
        class="input"
        confirm-type="send"
        placeholder="发送私信"
        @confirm="send"
      />
      <button class="send" @click="send">发送</button>
    </view>
  </view>
</template>

<script setup>
import { ref } from 'vue'
import { onLoad, onShow, onUnload } from '@dcloudio/uni-app'
import {
  getDirectMessages,
  markDirectChatRead,
  sendDirectMessage,
} from '../../utils/api.js'
import { getToken } from '../../utils/request.js'
import { formatChatTime } from '../../utils/time.js'

const threadId = ref('')
const peerNickname = ref('')
const messages = ref([])
const nextCursor = ref(null)
const loading = ref(false)
const loadingMore = ref(false)
const draft = ref('')
const scrollInto = ref('')
const myUserId = ref('')

let noMore = false

function syncMe() {
  const u = uni.getStorageSync('wm_user')
  myUserId.value = u && u.userId ? u.userId : ''
}

async function loadInitial() {
  if (!threadId.value) return
  loading.value = true
  noMore = false
  try {
    const data = await getDirectMessages(threadId.value, undefined, 30)
    messages.value = data.list || []
    nextCursor.value = data.nextCursor || null
    if (!data.nextCursor) noMore = true
    scrollBottom()
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

async function onScrollUpper() {
  if (loadingMore.value || noMore || !nextCursor.value) return
  loadingMore.value = true
  const anchor = messages.value[0]?.messageId
  try {
    const data = await getDirectMessages(threadId.value, nextCursor.value, 30)
    const older = data.list || []
    if (older.length) {
      messages.value = [...older, ...messages.value]
    }
    nextCursor.value = data.nextCursor || null
    if (!data.nextCursor) noMore = true
    if (anchor) {
      scrollInto.value = 'dm-' + anchor
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loadingMore.value = false
  }
}

function scrollBottom() {
  const last = messages.value[messages.value.length - 1]
  if (last) {
    setTimeout(() => {
      scrollInto.value = 'dm-' + last.messageId
    }, 80)
  }
}

async function send() {
  const t = (draft.value || '').trim()
  if (!t || !threadId.value) return
  try {
    const res = await sendDirectMessage(threadId.value, { msgType: 'text', text: t })
    draft.value = ''
    messages.value = [...messages.value, res]
    scrollBottom()
  } catch (e) {
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
  }
}

async function markRead() {
  try {
    await markDirectChatRead(threadId.value)
  } catch {
    /* ignore */
  }
}

onLoad((q) => {
  if (!getToken()) {
    uni.redirectTo({ url: '/pages/login/login' })
    return
  }
  syncMe()
  threadId.value = decodeURIComponent(q.threadId || '')
  peerNickname.value = decodeURIComponent(q.peerNickname || '')
  if (peerNickname.value) {
    uni.setNavigationBarTitle({ title: peerNickname.value })
  }
  loadInitial()
})

onShow(() => {
  markRead()
})

onUnload(() => {
  markRead()
})
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: #e9ecf1;
}
.scroll {
  flex: 1;
  padding: 24rpx;
  box-sizing: border-box;
}
.hint {
  text-align: center;
  color: #999;
}
.row {
  margin-bottom: 20rpx;
}
.bubble-wrap {
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
}
.bubble-wrap.me {
  flex-direction: row-reverse;
}
.avatar-sm {
  width: 64rpx;
  height: 64rpx;
  border-radius: 8rpx;
  background: #cfd8e6;
  color: #fff;
  font-size: 26rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.bubble {
  max-width: 74%;
  margin: 0 14rpx;
  padding: 16rpx 20rpx;
  border-radius: 16rpx;
  background: #fff;
}
.bubble.me {
  background: #cde8ff;
}
.text {
  font-size: 30rpx;
  word-break: break-all;
}
.img {
  max-width: 100%;
  border-radius: 8rpx;
}
.time {
  display: block;
  font-size: 20rpx;
  color: #999;
  margin-top: 8rpx;
}
.composer {
  display: flex;
  align-items: center;
  padding: 16rpx 24rpx 32rpx;
  background: #f7f7f8;
  border-top: 1rpx solid #ddd;
}
.input {
  flex: 1;
  padding: 16rpx 20rpx;
  background: #fff;
  border-radius: 12rpx;
  margin-right: 16rpx;
  font-size: 28rpx;
}
.send {
  background: #007aff;
  color: #fff;
  font-size: 28rpx;
  padding: 16rpx 28rpx;
  border-radius: 12rpx;
}
</style>
