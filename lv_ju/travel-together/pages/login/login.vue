<template>
  <view class="page">
    <view class="field">
      <text class="label">手机号</text>
      <input v-model="phone" class="input" type="number" maxlength="11" placeholder="11 位手机号" />
    </view>
    <view class="field row">
      <input v-model="code" class="input flex" type="number" maxlength="6" placeholder="验证码" />
      <button class="btn-ghost" :disabled="sending" @click="onSendCode">
        {{ sendLabel }}
      </button>
    </view>
    <button class="btn-primary" :disabled="loading" @click="onLogin">登录</button>
    <text class="tip">联调环境验证码为 123456（见后端 Mock）</text>
  </view>
</template>

<script setup>
import { ref, computed } from 'vue'
import { smsLogin, smsSend } from '../../utils/api.js'
import { setToken } from '../../utils/request.js'

const phone = ref('13800138000')
const code = ref('123456')
const loading = ref(false)
const sending = ref(false)
const countdown = ref(0)

const sendLabel = computed(() => {
  if (countdown.value > 0) return `${countdown.value}s`
  return sending.value ? '发送中…' : '获取验证码'
})

async function onSendCode() {
  if (!/^1\d{10}$/.test(phone.value)) {
    uni.showToast({ title: '请输入正确手机号', icon: 'none' })
    return
  }
  sending.value = true
  try {
    await smsSend(phone.value, 'login')
    uni.showToast({ title: '已发送', icon: 'none' })
    countdown.value = 60
    const t = setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0) clearInterval(t)
    }, 1000)
  } catch (e) {
    uni.showToast({ title: e.message || '发送失败', icon: 'none' })
  } finally {
    sending.value = false
  }
}

async function onLogin() {
  if (!/^1\d{10}$/.test(phone.value)) {
    uni.showToast({ title: '请输入正确手机号', icon: 'none' })
    return
  }
  loading.value = true
  try {
    const data = await smsLogin(phone.value, code.value)
    setToken(data.accessToken)
    if (data.user) {
      uni.setStorageSync('wm_user', data.user)
    }
    uni.showToast({ title: '登录成功', icon: 'success' })
    setTimeout(() => {
      uni.reLaunch({ url: '/pages/messages/messages' })
    }, 400)
  } catch (e) {
    uni.showToast({ title: e.message || '登录失败', icon: 'none' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.page {
  padding: 48rpx;
}
.field {
  margin-bottom: 32rpx;
}
.field.row {
  display: flex;
  align-items: center;
  gap: 16rpx;
}
.label {
  display: block;
  margin-bottom: 12rpx;
  color: #666;
  font-size: 26rpx;
}
.input {
  width: 100%;
  padding: 24rpx;
  background: #fff;
  border-radius: 12rpx;
  box-sizing: border-box;
}
.flex {
  flex: 1;
}
.btn-primary {
  margin-top: 24rpx;
  background: #007aff;
  color: #fff;
  border-radius: 12rpx;
  font-size: 30rpx;
}
.btn-ghost {
  font-size: 26rpx;
  padding: 16rpx 24rpx;
  background: #eef6ff;
  color: #007aff;
  border-radius: 12rpx;
}
.tip {
  display: block;
  margin-top: 32rpx;
  color: #999;
  font-size: 24rpx;
}
</style>
