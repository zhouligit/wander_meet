# WanderMeet Backend TODO（接口联通后）

更新时间：2026-05-20  
适用范围：当前 FastAPI + MySQL + Redis 后端

---

## 1. 当前仍为 Mock / 占位的能力

## 1.1 鉴权与登录

- [ ] 短信发送仍为 Mock：`POST /api/v1/wm/auth/sms/send` 仅写入 Redis，未接真实短信服务商。
- [ ] Refresh Token 为简化实现：`/auth/token/refresh` 仍是轻量逻辑，未实现完整双 token（access/refresh）体系与撤销机制。

## 1.2 用户与资料

- [ ] **头像（落库与全链路）**  
  - 现状：`users.avatar_url` 与 `PATCH /me` 的 `avatarUrl` 已可写库；`GET /me` 会返回 `avatarUrl`。  
  - 后端待做：`POST /me/avatar/upload-url` 仍返回占位地址，**需接阿里云 OSS（或同类）预签名上传**，并约定 `objectKey`、直传成功后的**可访问公网 URL** 规则。  
  - 小程序待做（`lv_ju/travel-together`）：`profile-edit` 目前仅为「昵称首字母」展示，**无** `chooseImage` / 直传 / `updateMe({ avatarUrl })` 回写；个人中心展示需改为优先 `image` + `avatarUrl`（有则显图、无则首字）。  
- [x] `users.tags` 已落库，`GET/PATCH /me` 已读写 `tags`（小程序编辑页若未接 UI，仍可能长期为空数组）。
- [ ] `GET /api/v1/wm/me` 中 `phoneMasked` 仍为占位逻辑（非真实手机号脱敏流程）。

## 1.3 认证与风控

- [ ] `GET/POST /api/v1/wm/me/verification` 已有基础入库，但未接实名/人脸三方服务。
- [ ] 认证审核工作流未完善：缺少审核队列、审核后台流程自动化、通知联动。
- [ ] 发活动认证门槛当前未强制（按当前产品决策先不强制）。

## 1.4 社交与通知

- [ ] IM 实时能力仍缺失：当前是接口拉取模式，未接 WebSocket 或第三方 IM。
- [ ] 通知系统为基础接口态，尚未全面打通业务事件自动入通知（如报名成功/活动变更/审核结果）。

## 1.5 商业化与系统任务

- [ ] 会员能力占位：`GET /api/v1/wm/me/premium` 固定 `enabled=false`。
- [ ] 定时任务未接入：活动自动结束、过期数据清理、失败重试等尚未有 worker/cron。

---

## 2. 后续建议优先级（建议执行顺序）

## P0（上线前必须）

- [ ] 接入真实短信服务（阿里云短信或腾讯云短信）。
- [ ] 补短信限流（按手机号/IP）与发送审计。
- [ ] JWT 密钥改为环境变量，完善 token 生命周期与撤销策略。
- [ ] 完善日志脱敏与统一错误码。

## P1（上线后高优先）

- [ ] 打通通知事件流（报名、取消、审核、举报处理）。
- [ ] 接入定时任务（活动自动结束、过期清理、补偿重试）。
- [ ] 落地 IM 实时方案（WebSocket 或第三方 IM）。
- [ ] 补齐认证审核流程（人工审核后台 + 状态回写）。

## P2（增长与运营阶段）

- [ ] 会员能力正式上线（权益、计费、状态同步）。
- [ ] 风控能力增强（更细粒度举报处理、自动策略）。
- [ ] 观测体系完善（监控、告警、慢查询分析、容量预估）。

---

## 3. 两个关键决策（需尽快拍板）

- [ ] 短信供应商选型：阿里云短信 / 腾讯云短信。
- [ ] IM 方案选型：自建 WebSocket / 第三方 IM。

---

## 4. 备注

- 当前接口可联调、主链路可跑通。
- 本文档用于将“可跑通版本”推进到“可上线版本”的执行清单。

---

## 5. 资料与引导

**产品进度（极简引导已上线）**：见 **`doc/WanderMeet_新手引导_产品与进度.md`**。  
全量步骤对照仍见 **`doc/WanderMeet_Nomadtable_Onboarding_对照.md`**。

### 5.1 数据库（`users` 表）

- [x] 引导扩展列：`country_code`、`traveler_roles`、`current_place`、`stay_kind`、`stay_end_at`、`acquisition_source`、`notify_prefs`、`show_distance`、`onboarding_completed_at`（迁移 `20260508_0009` 等）。
- [ ] 新环境部署时仍需执行 `alembic upgrade head`。

### 5.2 接口（`MeData` / `UpdateMeRequest`）

- [x] `GET /me`、`PATCH /me` 扩展字段与 `completeOnboarding`。
- [x] `GET /meta/onboarding`：词表 + **`fullOnboardingEnabled`**（`ONBOARDING_FULL_ENABLED`，默认关闭多步引导）。
- [ ] （可选）在线人数等运营数字：`GET /meta/stats` — 口径需产品定义。

### 5.3 其它（与引导相关）

- [ ] 头像：`POST /me/avatar/upload-url` 接 OSS（见 §1.2）。
- [ ] 通知偏好若落库需与后续推送通道对齐；若仅本地存储可暂不实现后端字段。

---

## 6. 备注（引导文档）

- 对照文档中的 **§5 接口与数据库变动草案** 随评审更新；实现后以代码与 OpenAPI 为准，并回写本文 §5 勾选状态。

---

## 7. 性能与缓存

详细清单与待办见 **`doc/PERF_Cache_and_Scale.md`**。

- [x] `GET /meta/activity-categories`、`/meta/onboarding`、`/meta/city-groups` 进程内 `@lru_cache`。
- [x] `GET /activities` 同城列表 Redis 短缓存（默认 60s）+ 发布/报名等写操作按 `city_code` 失效。
- [x] 迁移 `20260520_0018`：`activities(activity_kind, activity_status, end_at, start_at)` 复合索引。
- [x] `GET /activities/nearby` 短缓存；`GET /activities/{id}` 详情短缓存。
- [x] `GET /me/chats` 未读：普通活动 Redis 计数 + 城群 bounded COUNT（见 `doc/PERF_Cache_and_Scale.md`）。
- [x] `GET /me`、`/me/stats` 短缓存；鉴权用户行 Redis 缓存；`ended_at` 冗余 + 迁移 `20260521_0019`；meta `Cache-Control`。
- [ ] 读写分离与压测（暂不实施）。
- [ ] 定时任务：过期活动写 `ended_at` / 自动结束。
