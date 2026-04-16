# 旅聚 WanderMeet 数据库表设计 v0.1

对应 PRD：`PRD_WanderMeet_v0.1_Beijing.md`  
对应 API：`API_WanderMeet_v0.1.md`  

约定：

- 主键：`BIGINT` 自增或 `UUID`/`雪花` 字符串，下文用 `id`/`xxx_id` 统称。
- 时间：`created_at`、`updated_at` 为 `TIMESTAMPTZ`（UTC 存库，应用层转东八区）。
- 软删：v0.1 用户与活动关键表可先物理删 + 审计，或 `deleted_at` 可选。
- 字符集：`utf8mb4`，排序 `utf8mb4_unicode_ci`（MySQL 示例）。

---

## 1. `users` 用户

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | 用户主键 |
| phone_hash | VARCHAR(64) | UNIQUE, NOT NULL | 手机号哈希（不存明文，或 KMS 加密列） |
| phone_cipher | VARBINARY | NULL | 可选：可逆加密用于找回（敏感，慎存） |
| nickname | VARCHAR(32) | NOT NULL | 昵称 |
| avatar_url | VARCHAR(512) | NULL | 头像 URL |
| status | VARCHAR(16) | NOT NULL, DEFAULT `active` | `active` \| `banned` \| `restricted` |
| role | VARCHAR(16) | NOT NULL, DEFAULT `user` | `user` \| `admin` |
| last_login_at | TIMESTAMPTZ | NULL | 最近登录 |
| created_at | TIMESTAMPTZ | NOT NULL | 创建时间 |
| updated_at | TIMESTAMPTZ | NOT NULL | 更新时间 |

索引：

- `uniq_phone_hash` UNIQUE (`phone_hash`)
- `idx_status` (`status`)

---

## 2. `user_tags` 用户标签（多对多）

若标签固定枚举，可用位图或 JSON；规范化可用关联表。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| user_id | BIGINT | FK → users.id, NOT NULL | |
| tag_id | VARCHAR(32) | NOT NULL | 如 `digital_nomad`、`weekend` |

索引：

- `uniq_user_tag` UNIQUE (`user_id`, `tag_id`)
- `idx_tag` (`tag_id`)

---

## 3. `user_verifications` 组织者认证

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| user_id | BIGINT | FK, NOT NULL | |
| status | VARCHAR(16) | NOT NULL | `pending` \| `approved` \| `rejected` |
| real_name_cipher | VARBINARY | NULL | 姓名密文 |
| id_card_cipher | VARBINARY | NULL | 证件号密文（或仅存后四位 + 哈希） |
| face_verify_provider | VARCHAR(32) | NULL | 人脸服务商 |
| face_verify_ref | VARCHAR(256) | NULL | 人脸流水/流水号 |
| reject_reason | VARCHAR(512) | NULL | |
| submitted_at | TIMESTAMPTZ | NULL | |
| reviewed_at | TIMESTAMPTZ | NULL | |
| reviewer_admin_id | BIGINT | NULL | 人工审核人 |

索引：

- `idx_user` (`user_id`)
- `idx_status` (`status`)

说明：一人一条当前有效记录；重新提交可 `version` 字段或建新行仅最新 `approved` 有效。

---

## 4. `activities` 活动

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| public_id | VARCHAR(32) | UNIQUE | 对外 `act_xxx`，或直接 string PK |
| organizer_id | BIGINT | FK → users.id, NOT NULL | |
| title | VARCHAR(80) | NOT NULL | |
| description | TEXT | NOT NULL | |
| category_id | VARCHAR(32) | NOT NULL | coffee / citywalk / ... |
| city_code | VARCHAR(16) | NOT NULL | 如 `110000` |
| location_name | VARCHAR(128) | NOT NULL | |
| address_detail | VARCHAR(256) | NULL | |
| lat | DECIMAL(10,7) | NOT NULL | |
| lng | DECIMAL(10,7) | NOT NULL | |
| start_at | TIMESTAMPTZ | NOT NULL | |
| end_at | TIMESTAMPTZ | NULL | |
| max_members | INT | NOT NULL | 人数上限 |
| fee_type | VARCHAR(16) | NOT NULL | `free` \| `aa` \| `fixed` |
| fee_amount_cents | INT | NULL | 分 |
| rules_no_harassment | BOOLEAN | NOT NULL | PRD 勾选 |
| rules_no_promotion | BOOLEAN | NOT NULL | |
| rules_no_inappropriate | BOOLEAN | NOT NULL | |
| activity_status | VARCHAR(24) | NOT NULL | 见下 |
| cancel_reason | VARCHAR(512) | NULL | 组织者取消说明 |
| cancelled_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

`activity_status` 枚举建议：

- `pending_review` 待审核  
- `published` 已发布  
- `rejected` 审核拒绝  
- `cancelled` 已取消  
- `ended` 已结束（可由定时任务批量更新）

索引：

- `idx_city_start` (`city_code`, `start_at`)
- `idx_organizer` (`organizer_id`)
- `idx_status_start` (`activity_status`, `start_at`)
- `idx_lat_lng`（若需附近：可用 PostGIS 或冗余 geohash 列）

---

## 5. `activity_enrollments` 报名

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| activity_id | BIGINT | FK, NOT NULL | |
| user_id | BIGINT | FK, NOT NULL | |
| status | VARCHAR(16) | NOT NULL | `joined` \| `cancelled` |
| joined_at | TIMESTAMPTZ | NULL | |
| cancelled_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |
| updated_at | TIMESTAMPTZ | NOT NULL | |

索引：

- `uniq_activity_user` UNIQUE (`activity_id`, `user_id`) — 同一用户仅一条有效报名：可用部分唯一索引（PostgreSQL）或业务层保证 + `status`
- `idx_activity_status` (`activity_id`, `status`)

---

## 6. `activity_messages` 活动群聊消息

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| public_id | VARCHAR(32) | UNIQUE | `msg_xxx` |
| activity_id | BIGINT | FK, NOT NULL | |
| sender_id | BIGINT | FK, NOT NULL | |
| msg_type | VARCHAR(16) | NOT NULL | `text` \| `image` |
| text_content | TEXT | NULL | |
| image_url | VARCHAR(512) | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

索引：

- `idx_activity_created` (`activity_id`, `created_at`) — 分页拉历史
- `idx_sender` (`sender_id`)

说明：高风险内容可异步送审表，v0.1 可先信审 + 举报兜底。

---

## 7. `reports` 举报

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| reporter_id | BIGINT | FK, NOT NULL | |
| target_type | VARCHAR(16) | NOT NULL | `user` \| `activity` \| `message` |
| target_id | VARCHAR(64) | NOT NULL | 对应业务 ID 字符串 |
| activity_id | BIGINT | NULL | 上下文 |
| reason_code | VARCHAR(32) | NOT NULL | |
| detail | VARCHAR(1024) | NULL | |
| status | VARCHAR(16) | NOT NULL | `pending` \| `handled` \| `dismissed` |
| handled_action | VARCHAR(32) | NULL | 管理员处置类型 |
| handler_admin_id | BIGINT | NULL | |
| handled_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

索引：

- `idx_status_created` (`status`, `created_at`)
- `idx_target` (`target_type`, `target_id`)

---

## 8. `user_blocks` 拉黑

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| blocker_id | BIGINT | FK, NOT NULL | 拉黑方 |
| blocked_id | BIGINT | FK, NOT NULL | 被拉黑 |
| created_at | TIMESTAMPTZ | NOT NULL | |

索引：

- `uniq_block` UNIQUE (`blocker_id`, `blocked_id`)
- `idx_blocker` (`blocker_id`)

---

## 9. `notifications` 站内通知

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| user_id | BIGINT | FK, NOT NULL | 接收人 |
| type | VARCHAR(32) | NOT NULL | enrollment_ok / activity_changed / ... |
| title | VARCHAR(64) | NOT NULL | |
| body | VARCHAR(512) | NOT NULL | |
| payload_json | JSONB | NULL | `{ "activityId": "..." }` |
| read_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

索引：

- `idx_user_read` (`user_id`, `read_at`, `created_at`)

---

## 10. `sms_codes` 短信验证码（或用 Redis）

若全走 Redis，可省略此表；落库便于审计与风控。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| phone_hash | VARCHAR(64) | NOT NULL | |
| code_hash | VARCHAR(64) | NOT NULL | 仅存哈希 |
| scene | VARCHAR(16) | NOT NULL | `login` |
| expires_at | TIMESTAMPTZ | NOT NULL | |
| consumed_at | TIMESTAMPTZ | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

索引：`idx_phone_scene_exp` (`phone_hash`, `scene`, `expires_at`)

---

## 11. `admin_audit_logs` 管理操作审计（推荐）

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| id | BIGINT | PK | |
| admin_user_id | BIGINT | NOT NULL | |
| action | VARCHAR(64) | NOT NULL | approve_activity / ban_user / ... |
| target_type | VARCHAR(16) | NULL | |
| target_id | VARCHAR(64) | NULL | |
| detail_json | JSONB | NULL | |
| created_at | TIMESTAMPTZ | NOT NULL | |

---

## 12. ER 关系摘要

```
users 1 --- * activities (organizer)
users 1 --- * activity_enrollments
activities 1 --- * activity_enrollments
activities 1 --- * activity_messages
users 1 --- * user_blocks (blocker / blocked)
users 1 --- * reports (reporter)
users 1 --- * notifications
users 1 --- 1 user_verifications（或 1 对多版本）
```

---

## 13. 与 PRD 能力映射

| PRD 能力 | 主要表 |
| --- | --- |
| 手机号登录 | users、sms_codes（或 Redis） |
| 资料与标签 | users、user_tags |
| 发活动需认证 | user_verifications、activities |
| 活动流与筛选 | activities |
| 报名 | activity_enrollments |
| 活动群聊 | activity_messages |
| 举报/拉黑/封禁 | reports、user_blocks、users.status |
| 通知 | notifications |
| 审核活动 | activities.activity_status、admin_audit_logs |
| 埋点（可选） | 独立 events 表或由分析平台 SDK，不阻塞 v0.1 |

---

文档版本：v0.1  
