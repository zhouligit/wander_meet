import { API_BASE } from './config.js'

const TOKEN_KEY = 'wm_access_token'

export function getToken() {
  return uni.getStorageSync(TOKEN_KEY) || ''
}

export function setToken(t) {
  if (t) {
    uni.setStorageSync(TOKEN_KEY, t)
  } else {
    uni.removeStorageSync(TOKEN_KEY)
  }
}

/**
 * @param {{ url: string, method?: string, data?: object, query?: Record<string,string|number> }} opts
 */
export function request(opts) {
  const { url, method = 'GET', data, query } = opts
  let full = `${API_BASE}${url.startsWith('/') ? '' : '/'}${url}`
  if (query && Object.keys(query).length) {
    const q = Object.entries(query)
      .filter(([, v]) => v !== undefined && v !== null && v !== '')
      .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
      .join('&')
    full += (full.includes('?') ? '&' : '?') + q
  }
  const token = getToken()
  return new Promise((resolve, reject) => {
    uni.request({
      url: full,
      method,
      data: method === 'GET' ? undefined : data,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success(res) {
        const body = res.data
        if (!body || typeof body !== 'object') {
          reject(new Error('无效响应'))
          return
        }
        if (body.code !== 0) {
          const err = new Error(body.message || '请求失败')
          err.code = body.code
          err.payload = body.data
          reject(err)
          return
        }
        resolve(body.data)
      },
      fail(e) {
        reject(e || new Error('网络错误'))
      },
    })
  })
}
