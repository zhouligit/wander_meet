<template>
  <view class="page">
    <view v-if="loading" class="hint">加载中…</view>
    <template v-else-if="profile">
      <view class="head">
        <view class="avatar-lg">{{ profile.nickname.slice(0, 1) }}</view>
        <text class="name">{{ profile.nickname }}</text>
        <text v-if="profile.verificationBadge" class="badge">已认证</text>
      </view>
      <view class="block">
        <text class="label">简介</text>
        <text class="bio">{{ profile.bio || '暂无简介' }}</text>
      </view>
      <view v-if="profile.tags?.length" class="block">
        <text class="label">标签</text>
        <view class="tags">
          <text v-for="(t, i) in profile.tags" :key="i" class="tag">{{ t }}</text>
        </view>
      </view>
      <view class="dm-area">
        <button
          v-if="ctx.threadId"
          class="btn-primary"
          @click="openDirect(ctx.threadId)"
        >
          进入私聊
        </button>
        <template v-else-if="ctx.incomingPendingRequestId">
          <text class="note">对方申请与你私聊</text>
          <view class="row-btns">
            <button class="btn-primary" @click="acceptIncoming">同意</button>
            <button class="btn-danger" @click="rejectIncoming">拒绝</button>
          </view>
        </template>
        <template v-else-if="ctx.outgoingPendingRequestId">
          <button class="btn-disabled" disabled>已发送申请，等待对方同意</button>
          <button class="btn-ghost" @click="cancelOutgoing">撤回申请</button>
        </template>
        <template v-else-if="ctx.canRequest">
          <view v-if="showIntro" class="intro-box">
            <textarea
              v-model="introDraft"
              class="textarea"
              placeholder="选填附言，让对方知道你是谁"
              maxlength="500"
            />
            <button class="btn-primary" @click="submitRequest">发送申请</button>
            <button class="btn-ghost" @click="showIntro = false">取消</button>
          </view>
          <button v-else class="btn-primary" @click="showIntro = true">申请私聊</button>
        </template>
        <text v-else class="note">{{ denyText }}</text>
      </view>
    </template>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import {
  acceptDmRequest,
  cancelDmRequest,
  createDmRequest,
  getUserDmContext,
  getUserPublic,
  rejectDmRequest,
} from '../../utils/api.js'
import { getToken } from '../../utils/request.js'

const userId = ref('')
const activityId = ref('')
const profile = ref(null)
const ctx = ref({
  threadId: null,
  outgoingPendingRequestId: null,
  incomingPendingRequestId: null,
  canRequest: false,
  denyReason: null,
})
const loading = ref(true)
const showIntro = ref(false)
const introDraft = ref('')

const denyText = computed(() => {
  const r = ctx.value.denyReason
  const map = {
    self: '这是你自己',
    blocked: '无法发起（已拉黑或被对方拉黑）',
    not_in_activity: '你不在该活动中',
    target_not_in_activity: '对方不在该活动中',
    has_thread: '已与对方开通私聊',
    pending_outgoing: '已发送申请',
    pending_incoming: '对方已向你发起申请',
    not_found: '用户不存在',
  }
  return map[r] || (r ? `暂不可申请（${r}）` : '')
})

async function load() {
  loading.value = true
  try {
    const [pub, dm] = await Promise.all([
      getUserPublic(userId.value),
      getUserDmContext(userId.value, activityId.value),
    ])
    profile.value = pub
    ctx.value = {
      threadId: dm.threadId || null,
      outgoingPendingRequestId: dm.outgoingPendingRequestId || null,
      incomingPendingRequestId: dm.incomingPendingRequestId || null,
      canRequest: !!dm.canRequest,
      denyReason: dm.denyReason || null,
    }
  } catch (e) {
    uni.showToast({ title: e.message || '加载失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}

function openDirect(threadId) {
  uni.navigateTo({
    url:
      '/pages/direct-chat-detail/direct-chat-detail?threadId=' +
      encodeURIComponent(threadId) +
      '&peerNickname=' +
      encodeURIComponent(profile.value?.nickname || ''),
  })
}

async function submitRequest() {
  const introText = introDraft.value.trim() || undefined
  try {
    await createDmRequest(activityId.value, {
      toUserId: userId.value,
      introText,
    })
    uni.showToast({ title: '已发送', icon: 'success' })
    showIntro.value = false
    introDraft.value = ''
    await load()
  } catch (e) {
    if (e.code === 409 && e.payload?.threadId) {
      showIntro.value = false
      openDirect(e.payload.threadId)
      return
    }
    if (e.code === 409 && e.payload?.requestId) {
      uni.showToast({
        title:
          e.message === 'incoming request exists'
            ? '对方已申请你，请到「私聊申请」处理'
            : e.message || '重复申请',
        icon: 'none',
      })
      await load()
      return
    }
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
  }
}

async function acceptIncoming() {
  const id = ctx.value.incomingPendingRequestId
  if (!id) return
  try {
    const data = await acceptDmRequest(id)
    uni.showToast({ title: '已同意', icon: 'success' })
    openDirect(data.threadId)
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  }
}

async function rejectIncoming() {
  const id = ctx.value.incomingPendingRequestId
  if (!id) return
  try {
    await rejectDmRequest(id)
    uni.showToast({ title: '已拒绝', icon: 'none' })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  }
}

async function cancelOutgoing() {
  const id = ctx.value.outgoingPendingRequestId
  if (!id) return
  try {
    await cancelDmRequest(id)
    uni.showToast({ title: '已撤回', icon: 'none' })
    await load()
  } catch (e) {
    uni.showToast({ title: e.message || '操作失败', icon: 'none' })
  }
}

onLoad((q) => {
  if (!getToken()) {
    uni.redirectTo({ url: '/pages/login/login' })
    return
  }
  userId.value = decodeURIComponent(q.userId || '')
  activityId.value = decodeURIComponent(q.activityId || '')
  if (!userId.value || !activityId.value) {
    uni.showToast({ title: '缺少参数', icon: 'none' })
    return
  }
  load()
})
</script>

<style scoped>
.page {
  padding: 32rpx;
  min-height: 100vh;
}
.hint {
  text-align: center;
  color: #999;
}
.head {
  align-items: center;
  display: flex;
  flex-direction: column;
  padding: 32rpx 0;
}
.avatar-lg {
  width: 140rpx;
  height: 140rpx;
  border-radius: 70rpx;
  background: linear-gradient(135deg, #6eb6ff, #007aff);
  color: #fff;
  font-size: 56rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20rpx;
}
.name {
  font-size: 40rpx;
  font-weight: 600;
}
.badge {
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #007aff;
}
.block {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 24rpx;
}
.label {
  font-size: 24rpx;
  color: #888;
  display: block;
  margin-bottom: 12rpx;
}
.bio {
  font-size: 28rpx;
  line-height: 1.5;
}
.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 12rpx;
}
.tag {
  background: #eef6ff;
  color: #007aff;
  padding: 8rpx 16rpx;
  border-radius: 8rpx;
  font-size: 24rpx;
}
.dm-area {
  margin-top: 24rpx;
}
.btn-primary {
  background: #007aff;
  color: #fff;
  border-radius: 12rpx;
  font-size: 30rpx;
  margin-bottom: 16rpx;
}
.btn-danger {
  background: #ff3b30;
  color: #fff;
  border-radius: 12rpx;
  font-size: 30rpx;
}
.btn-disabled {
  background: #ccc;
  color: #fff;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
}
.btn-ghost {
  background: transparent;
  color: #007aff;
  font-size: 28rpx;
}
.row-btns {
  display: flex;
  gap: 24rpx;
}
.row-btns button {
  flex: 1;
}
.note {
  display: block;
  color: #666;
  font-size: 26rpx;
  margin-bottom: 16rpx;
}
.intro-box {
  margin-top: 8rpx;
}
.textarea {
  width: 100%;
  min-height: 160rpx;
  padding: 16rpx;
  background: #fff;
  border-radius: 12rpx;
  margin-bottom: 16rpx;
  box-sizing: border-box;
  font-size: 28rpx;
}
</style>
