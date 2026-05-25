# 抖音小程序登录（后端）

更新时间：2026-05-23

## 接口

`POST /api/v1/wm/auth/douyin/login`

请求体（camelCase）：

```json
{ "code": "tt.login 返回的 code" }
```

响应与短信 / 微信登录相同：`accessToken`、`refreshToken`、`expiresIn`、`user`。

## 环境变量

```bash
DY_MP_APPID=抖音小程序 AppID
DY_MP_APPSECRET=AppSecret（仅服务端）
DY_MP_USE_MOCK=false   # 本地 true 时不调抖音，用 code 派生 mock openid
```

## 数据库

迁移 `20260523_0021`：`users.dy_openid`（UNIQUE）。

新用户 `phone_hash = sha256("dy:" + openid)`，`acquisition_source = mp_douyin`。

## 绑手机

抖音端使用已有 `POST /me/phone/bind-sms`（短信验证码）；合并账号时校验 `dy_openid` 冲突。

## 参考

- 微信对照：`doc/wx_login.md`、`POST /auth/wechat/login`
- 前端：`lv_ju/travel-together/src/utils/douyinAuth.js`、`login.vue`（`MP-TOUTIAO`）
