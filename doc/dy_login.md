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

## 联调排错

Console 出现 `[douyin] silent login failed: ...` 且 message 含 **Invalid / appid / secret**：

1. **`tt.login` 已成功**，失败在服务器调抖音 `code2session`。
2. 服务器 `.env` 必须与开发者工具 **同一小程序**：
   - `DY_MP_APPID=tt631715aafd7006cf01`（与 `manifest.json` → `mp-toutiao.appid` 一致）
   - `DY_MP_APPSECRET=` 开放平台 **开发设置 → AppSecret**（一行字符串，不是公钥）
   - `DY_MP_USE_MOCK=false`（生产/真机联调）
3. 改 `.env` 后：`systemctl restart wandermeet`
4. 看日志：`journalctl -u wandermeet -f | grep douyin` → `err_no` / `err_tips`
   - **40015**：appid 错或与小程序不一致
   - **40017**：secret 错
   - **40018**：code 无效（多为 appid 不一致，或 code 重复使用）

本地仅前端、不接抖音开放平台：服务器设 `DY_MP_USE_MOCK=true` 可跳过 code2session。
