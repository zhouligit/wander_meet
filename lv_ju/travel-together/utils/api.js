import { request } from './request.js'

/** @param {string} activityId act_* */
export function getActivityMessages(activityId, cursor, limit = 20) {
  return request({
    url: `/activities/${activityId}/messages`,
    query: { cursor, limit },
  })
}

export function sendActivityMessage(activityId, payload) {
  return request({
    url: `/activities/${activityId}/messages`,
    method: 'POST',
    data: payload,
  })
}

export function markActivityChatRead(activityId) {
  return request({
    url: `/me/chats/${activityId}/read`,
    method: 'PATCH',
  })
}

export function getMyChats(page = 1, pageSize = 50) {
  return request({
    url: '/me/chats',
    query: { page, pageSize },
  })
}

export function getUserPublic(userId) {
  return request({ url: `/users/${encodeURIComponent(userId)}/public` })
}

/** @param {string} activityId act_* */
export function getUserDmContext(userId, activityId) {
  return request({
    url: `/users/${encodeURIComponent(userId)}/dm-context`,
    query: { activityId },
  })
}

/** @param {{ toUserId: string, introText?: string }} body */
export function createDmRequest(activityId, body) {
  return request({
    url: `/activities/${activityId}/dm-requests`,
    method: 'POST',
    data: body,
  })
}

export function listDmRequests(direction = 'incoming', status = 'pending', page = 1) {
  return request({
    url: '/me/dm-requests',
    query: { direction, status, page, pageSize: 50 },
  })
}

export function acceptDmRequest(requestId) {
  return request({
    url: `/me/dm-requests/${requestId}/accept`,
    method: 'POST',
  })
}

export function rejectDmRequest(requestId) {
  return request({
    url: `/me/dm-requests/${requestId}/reject`,
    method: 'POST',
  })
}

export function cancelDmRequest(requestId) {
  return request({
    url: `/me/dm-requests/${requestId}`,
    method: 'DELETE',
  })
}

export function getDirectChats(page = 1, pageSize = 50) {
  return request({
    url: '/me/direct-chats',
    query: { page, pageSize },
  })
}

export function getDirectMessages(threadId, cursor, limit = 20) {
  return request({
    url: `/direct-chats/${threadId}/messages`,
    query: { cursor, limit },
  })
}

export function sendDirectMessage(threadId, payload) {
  return request({
    url: `/direct-chats/${threadId}/messages`,
    method: 'POST',
    data: payload,
  })
}

export function markDirectChatRead(threadId) {
  return request({
    url: `/direct-chats/${threadId}/read`,
    method: 'PATCH',
  })
}

export function smsSend(phone, scene = 'login') {
  return request({
    url: '/auth/sms/send',
    method: 'POST',
    data: { phone, scene },
  })
}

export function smsLogin(phone, code) {
  return request({
    url: '/auth/sms/login',
    method: 'POST',
    data: { phone, code },
  })
}
