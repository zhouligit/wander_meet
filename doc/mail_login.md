# 邮箱登录（H5）— 前后端协作说明

更新时间：2026-05-18  
基路径：`https://<域名>/api/v1/wm`  
鉴权：登录成功后 `Authorization: Bearer <accessToken>`

> 本文档面向 **H5 Web** 与后端联调。微信小程序继续使用 **微信登录 + 绑定手机号**，不在 H5 做邮箱登录入口。

---

## 一、产品边界

| 端 | 登录方式 | 账号体系 |
| --- | --- | --- |
| **H5** | 邮箱 + 密码（注册 / 登录） | 独立邮箱账号 |
| **微信小程序** | 微信一键登录；可选绑定手机号 | `mp_openid` + 可选真实手机号 |

**v1 明确不做：**

- 邮件验证码注册 / 登录
- 邮箱与微信 / 手机号 **自动合并**（避免串号）
- 已登录修改密码（可列后续）
- 小程序内邮箱登录

**二期（忘记密码，已实现）：** 邮件验证码重置密码，见 §3.6。

**与现有能力关系：**

- 短信、微信登录接口不变；token 结构相同（`accessToken` + `refreshToken`）。
- 若同一人既有 H5 邮箱号又有小程序微信号，v1 为 **两条用户**；需运维合并见 `API_WanderMeet_v0.1.md` §36.2（一般不合并邮箱与微信，除非产品另定）。

---

## 二、前端（H5）要做的事

### 2.1 页面

| 页面 | 说明 |
| --- | --- |
| 注册 | 邮箱、密码、确认密码（前端校验）、可选昵称；协议勾选 |
| 登录 | 邮箱、密码 |
| 忘记密码 | `pages/forgot-password/forgot-password`（H5）；登录页「忘记密码？」入口 |
| 个人中心 | 展示 `GET /me` 的 `emailMasked`（`emailBound=true` 时） |

### 2.2 请求与存储

- **注册**：`POST /auth/email/register` → 成功即写入 token（与登录相同，**无需再调 login**）。
- **登录**：`POST /auth/email/login`。
- **忘记密码**：`POST /auth/email/forgot-password` → `POST /auth/email/reset-password`（响应与登录相同）。
- **Storage**（与小程序对齐，便于复用 HTTP 客户端）：
  - `wm_access_token`
  - `wm_refresh_token`
- **401**：走现有 `POST /auth/token/refresh`；失败清空 token 并跳转登录页。
- **基路径**：与小程序相同，如 `https://www.wang-hao-hao.cn/api/v1/wm`。

### 2.3 校验（前端）

| 项 | 规则 |
| --- | --- |
| 邮箱 | 非空；格式大致合法（后端为准） |
| 密码 | ≥8 位；至少 1 个字母 + 1 个数字 |
| 确认密码 | 与密码一致 |

### 2.4 错误展示（HTTP / message）

| HTTP | 场景 | 建议文案 |
| --- | --- | --- |
| 400 | 邮箱或密码格式不对 | 展示 `detail` |
| 401 | 邮箱或密码错误 | 「邮箱或密码错误」 |
| 409 | 邮箱已注册 | 「该邮箱已注册，请直接登录」 |
| 429 | 限流 / 登录锁定 | 展示 `detail` 或「操作过于频繁」 |
| 403 | 账号封禁 | 「账号不可用」 |

### 2.5 未登录与路由

- 需登录页：无 token 或 refresh 失败 → 跳转 H5 登录页。
- 已登录访问登录/注册页 → 跳转首页。

### 2.6 CORS

- H5 域名需在后端 `APP_CORS_ORIGINS` 中（逗号分隔），生产必须 **HTTPS**。

---

## 三、后端实现（已完成）

### 3.1 数据模型（`users` 表）

| 字段 | 说明 |
| --- | --- |
| `email` | 规范化小写邮箱，`UNIQUE`，可空 |
| `password_hash` | bcrypt（cost 12），可空 |
| `phone_hash` | 邮箱用户占位：`sha256("email:" + email)`，与手机 / 微信占位区分 |
| `phone` | 邮箱用户为 `NULL` |
| `mp_openid` | 邮箱用户为 `NULL` |

迁移：`alembic/versions/20260518_0015_user_email_auth.py`

### 3.2 API（与 `/auth/sms/*` 对称）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/auth/email/register` | 注册并下发 token |
| POST | `/auth/email/login` | 登录 |
| POST | `/auth/email/forgot-password` | 发送重置验证码（防枚举，统一成功） |
| POST | `/auth/email/reset-password` | 验证码 + 新密码，下发 token |

请求 / 响应详见 **`doc/API_WanderMeet_v0.1.md` §2.2–§2.3.2**。

### 3.3 与短信 / 微信接口关系

| 能力 | 短信 | 微信 | 邮箱 |
| --- | --- | --- | --- |
| 注册即登录 | 是（验证码登录） | 是（code 登录） | 是（register 返回 token） |
| refresh / logout | 共用 | 共用 | 共用 |
| `GET /me` | 共用 | 共用 | 增加 `emailMasked` / `emailBound` |

### 3.4 安全与运维

- 密码：bcrypt cost 12（依赖 `bcrypt>=4.0`）。
- 限流：IP 维度 `email_register` / `email_login`；同邮箱注册间隔；连续登录失败 5 次锁定 15 分钟（可配置）。
- 审计：注册 / 登录失败写应用日志（IP 在 access log / `X-Forwarded-For`）。
- **不**在 `GET /me` 返回是否设置密码等字段。

环境变量见 `.env.example` 中 `AUTH_EMAIL_*`、`EMAIL_*`、`SMTP_*`。

### 3.5 `GET /me` 扩展

| 字段 | 说明 |
| --- | --- |
| `emailMasked` | 如 `u***@example.com`；未绑定邮箱账号时为空字符串 |
| `emailBound` | 是否邮箱密码账号 |

### 3.6 忘记密码（二期）

| 步骤 | 接口 | 说明 |
| --- | --- | --- |
| 1 | `POST /auth/email/forgot-password` | Body `{ "email" }`；返回 `expireInSeconds` |
| 2 | `POST /auth/email/reset-password` | Body `{ "email", "code", "newPassword" }`；camelCase |

- Redis：`wm:email:reset:{email}` → 6 位验证码；`wm:email:forgot:rate:{email}` 发信间隔。
- **防枚举**：未注册邮箱也返回 200 + `expireInSeconds`，但不发信。
- 重置成功：更新 `password_hash`、清除登录失败锁、**吊销全部 refresh**，并签发新 access/refresh。

### 3.7 邮箱账号绑定手机号

- 调用 `POST /me/phone/bind-sms`（`scene=bind_phone`），与微信绑手机同一套逻辑。
- 若该手机号**已被**「微信 + 手机」或「短信」账号占用：邮箱账号**并入**该账号（`merged=true`，下发新 token），并**保留**邮箱与密码（合并后仍可用邮箱登录）。
- 仅当当前账号与目标账号**均为不同微信 openid** 时返回 409。
- 生产：`EMAIL_USE_MOCK=false`，配置 SMTP（465 SSL 或 587 STARTTLS）。
- 开发：`EMAIL_USE_MOCK=true` 时验证码固定为 `EMAIL_MOCK_CODE`（默认 `123456`），日志可见正文。

---

## 四、联调检查清单

- [ ] H5 注册成功 → Storage 有 `wm_access_token` / `wm_refresh_token`
- [ ] `GET /me` → `emailBound: true`，`emailMasked` 非空
- [ ] 错误密码 → 401，多次后 429 锁定
- [ ] 重复注册 → 409
- [ ] 小程序账号与 H5 邮箱账号 **不**自动合并（各登录各的 id）
- [x] 忘记密码页：发码 → 重置并登录（`travel-together` H5）
- [ ] 忘记密码：已注册邮箱收到验证码（或 Mock 日志）；重置后可用新密码登录
- [ ] 未注册邮箱调 forgot-password 仍 200，但无邮件

---

## 五、API 文档索引

- 邮箱注册 / 登录 / 忘记密码：**`doc/API_WanderMeet_v0.1.md` §2.2、§2.3、§2.3.1、§2.3.2**
- 微信登录：§2.1
- 绑定手机号：§4.1、§4.2
- 运维合并账号：§36.2
