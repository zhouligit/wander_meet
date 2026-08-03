# WanderMeet 数据库设计文档

> 生成时间：2026-07-30
> 数据库版本：MySQL 8.0+
> 字符集：utf8mb4
> 迁移版本：20260723_0033（共 33 个迁移）

---

## 目录

1. [核心业务表](#1-核心业务表)
2. [用户与认证](#2-用户与认证)
3. [私信系统](#3-私信系统)
4. [活动互动](#4-活动互动)
5. [增长与信任体系](#5-增长与信任体系)
6. [内容社区](#6-内容社区)
7. [城市群组管理](#7-城市群组管理)
8. [支付与订单](#8-支付与订单)
9. [举报与反馈](#9-举报与反馈)

---

## 1. 核心业务表

### 1.1 users（用户表）

系统核心用户表，支持多种登录方式（微信、抖音、邮箱+密码）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK AUTO_INCREMENT | 用户ID |
| phone | VARCHAR(20) | 手机号（明文，可为空） |
| phone_hash | VARCHAR(64) UNIQUE | 手机号 SHA256 哈希 |
| mp_openid | VARCHAR(64) UNIQUE | 微信小程序 openid |
| mp_unionid | VARCHAR(64) | 微信 unionid |
| dy_openid | VARCHAR(64) UNIQUE | 抖音小程序 openid |
| email | VARCHAR(254) UNIQUE | 邮箱（H5 登录） |
| password_hash | VARCHAR(255) | bcrypt 密码哈希 |
| nickname | VARCHAR(32) | 昵称 |
| gender | VARCHAR(16) | 性别 |
| birth_date | DATE | 出生日期 |
| avatar_url | VARCHAR(512) | 头像 URL |
| bio | TEXT | 个人简介 |
| tags | JSON | 兴趣标签数组 |
| country_code | VARCHAR(8) | 国家代码 |
| traveler_roles | JSON | 旅行者角色 |
| current_place | VARCHAR(256) | 当前位置 |
| stay_kind | VARCHAR(32) | 住宿类型 |
| stay_end_at | DATETIME | 住宿结束时间 |
| acquisition_source | VARCHAR(64) | 获客来源 |
| notify_prefs | JSON | 通知偏好设置 |
| show_distance | BOOL DEFAULT 1 | 是否显示距离 |
| onboarding_completed_at | DATETIME | 新手引导完成时间 |
| enrollment_identity_name | VARCHAR(32) | 报名实名-姓名 |
| enrollment_identity_id_card | VARCHAR(32) | 报名实名-身份证 |
| status | VARCHAR(16) DEFAULT 'active' | 账号状态 |
| role | VARCHAR(16) DEFAULT 'user' | 角色（user/admin） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**索引**：
- `idx_users_phone` (phone)
- `idx_users_phone_hash` (phone_hash)
- `uniq_users_mp_openid` (mp_openid)
- `idx_users_mp_unionid` (mp_unionid)
- `uniq_users_dy_openid` (dy_openid)
- `uniq_users_email` (email)

---

### 1.2 activities（活动表）

活动主表，支持普通活动（event）和城市大群（city_hall，虚拟活动）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK AUTO_INCREMENT | 活动ID |
| activity_kind | VARCHAR(20) DEFAULT 'event' | 活动类型：event / city_hall |
| city_hall_province_code | VARCHAR(8) | 城市大群-省份代码（XX0000） |
| city_hall_sort_key | VARCHAR(64) | 城市大群-排序键 |
| city_hall_city_code | VARCHAR(32) UNIQUE | 城市大群-城市代码 |
| organizer_id | BIGINT | 组织者用户ID |
| title | VARCHAR(80) | 活动标题 |
| description | TEXT | 活动描述 |
| category_id | VARCHAR(32) | 一级分类 |
| category_label | VARCHAR(32) | 自定义分类标签（category_id=other 时） |
| sub_category_id | VARCHAR(32) | 二级分类 |
| city_code | VARCHAR(16) | 城市代码 |
| location_name | VARCHAR(128) | 地点名称 |
| address_detail | VARCHAR(256) | 详细地址 |
| lat / lng | NUMERIC(10,7) | 经纬度 |
| start_at | DATETIME | 开始时间 |
| end_at | DATETIME | 计划结束时间 |
| ended_at | DATETIME | 实际结束/取消时间（冗余，用于索引排序） |
| max_members | INTEGER | 最大参与人数 |
| fee_type | VARCHAR(16) DEFAULT 'free' | 费用类型 |
| fee_amount_cents | INTEGER | 费用金额（分） |
| activity_status | VARCHAR(24) DEFAULT 'published' | 状态 |
| cover_image_url | VARCHAR(512) | 封面图 URL |
| images | JSON | 图片 URL 数组 |
| images_audit_status | VARCHAR(16) DEFAULT 'none' | 图片审核状态（none/pending/pass/reject） |
| images_audit_updated_at | DATETIME | 审核更新时间 |
| guide_sections | JSON | 活动说明章节 |
| require_enrollment_identity | BOOL DEFAULT 0 | 是否要求实名报名 |
| created_at / updated_at | DATETIME | 时间戳 |

**核心索引**：
- `idx_activities_city_code` (city_code)
- `idx_activities_status_start` (activity_status, start_at)
- `idx_activities_city_status_start` (city_code, activity_status, start_at)
- `idx_activities_kind_status_end_start` (activity_kind, activity_status, end_at, start_at)
- `idx_activities_ended_at` (ended_at)
- `idx_activities_organizer_ended` (organizer_id, ended_at)
- `ix_activities_sub_category_id` (sub_category_id)
- `uq_activities_city_hall_city_code` (city_hall_city_code)

---

### 1.3 activity_enrollments（活动报名表）

用户报名参与活动的记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK AUTO_INCREMENT | 报名记录ID |
| activity_id | BIGINT | 活动ID |
| user_id | BIGINT | 用户ID |
| status | VARCHAR(16) DEFAULT 'joined' | 状态 |
| participant_name | VARCHAR(32) | 实名-姓名 |
| id_card_number | VARCHAR(32) | 实名-身份证 |
| participant_phone | VARCHAR(20) | 实名-手机号 |
| created_at / updated_at | DATETIME | 时间戳 |

**约束**：`UNIQUE (activity_id, user_id)` — 一人只能报名一次

**索引**：
- `idx_activity_enrollments_activity_status` (activity_id, status)
- `idx_activity_enrollments_user_status_activity` (user_id, status, activity_id)

---

## 2. 用户与认证

### 2.1 user_verifications（实名认证表）

用户提交的实名认证申请（姓名+身份证+人脸）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| user_id | BIGINT | 用户ID |
| status | VARCHAR(16) DEFAULT 'pending' | 审核状态 |
| real_name | VARCHAR(32) | 真实姓名 |
| id_card_number | VARCHAR(32) | 身份证号 |
| face_verify_token | VARCHAR(256) | 人脸验证 token |
| reject_reason | VARCHAR(512) | 拒绝原因 |
| submitted_at | DATETIME | 提交时间 |
| reviewed_at | DATETIME | 审核时间 |
| created_at / updated_at | DATETIME | 时间戳 |

**索引**：`idx_user_verifications_user_status` (user_id, status)

---

## 3. 私信系统

### 3.1 dm_threads（私信会话表）

一对一私信会话，用 user_low_id / user_high_id 规范化存储（小ID在前）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 会话ID |
| user_low_id | BIGINT | 较小用户ID |
| user_high_id | BIGINT | 较大用户ID |
| created_at / updated_at | DATETIME | 时间戳 |

**约束**：`UNIQUE (user_low_id, user_high_id)`

---

### 3.2 dm_requests（私信请求表）

用户发起的私信请求，对方接受后创建 thread。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 请求ID |
| activity_id | BIGINT | 关联活动ID |
| from_user_id | BIGINT | 发起者 |
| to_user_id | BIGINT | 接收者 |
| intro_text | VARCHAR(500) | 自我介绍 |
| status | VARCHAR(16) DEFAULT 'pending' | 状态 |
| thread_id | BIGINT FK→dm_threads | 接受后创建的会话ID（ON DELETE SET NULL） |
| created_at | DATETIME | 创建时间 |
| responded_at | DATETIME | 响应时间 |

**索引**：
- `idx_dm_requests_to_status` (to_user_id, status)
- `idx_dm_requests_from_status` (from_user_id, status)
- `idx_dm_requests_activity` (activity_id)

---

### 3.3 direct_messages（私信消息表）

私信消息内容。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 消息ID |
| thread_id | BIGINT FK→dm_threads | 会话ID（ON DELETE CASCADE） |
| sender_id | BIGINT | 发送者 |
| msg_type | VARCHAR(16) DEFAULT 'text' | 消息类型 |
| text_content | TEXT | 文本内容 |
| image_url | VARCHAR(512) | 图片 URL |
| created_at | DATETIME | 创建时间 |

**索引**：
- `idx_direct_messages_thread_created` (thread_id, created_at)
- `idx_direct_messages_thread_id_id` (thread_id, id)

---

### 3.4 dm_thread_reads（私信已读状态表）

用户私信会话的已读游标。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| user_id | BIGINT | 用户ID |
| thread_id | BIGINT FK→dm_threads | 会话ID（ON DELETE CASCADE） |
| last_read_message_id | BIGINT DEFAULT 0 | 已读的最后一条消息ID |
| updated_at | DATETIME | 更新时间（ON UPDATE CURRENT_TIMESTAMP） |
| created_at | DATETIME | 创建时间 |

**约束**：`UNIQUE (user_id, thread_id)`

---

### 3.5 dm_thread_removals（私信删除表）

用户单方面删除好友/会话，可恢复。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| user_id | BIGINT | 操作用户 |
| thread_id | BIGINT FK→dm_threads | 被删除的会话（ON DELETE CASCADE） |
| removed_at | DATETIME | 删除时间 |

**约束**：`UNIQUE (user_id, thread_id)`

---

## 4. 活动互动

### 4.1 activity_messages（活动群聊消息表）

活动内的群聊消息，支持软删除。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 消息ID |
| activity_id | BIGINT | 活动ID |
| sender_id | BIGINT | 发送者 |
| msg_type | VARCHAR(16) DEFAULT 'text' | 消息类型 |
| text_content | TEXT | 文本内容 |
| image_url | VARCHAR(512) | 图片 URL |
| created_at | DATETIME | 创建时间 |
| deleted_at | DATETIME NULL | 软删除时间 |

**索引**：
- `idx_activity_messages_activity_created` (activity_id, created_at)
- `idx_activity_messages_activity_id_id` (activity_id, id)
- `ix_activity_messages_deleted_at` (deleted_at)

---

### 4.2 user_chat_reads（群聊已读状态表）

用户活动群聊的已读游标。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| user_id | BIGINT | 用户ID |
| activity_id | BIGINT | 活动ID |
| last_read_message_id | BIGINT DEFAULT 0 | 已读游标 |
| updated_at / created_at | DATETIME | 时间戳 |

**约束**：`UNIQUE (user_id, activity_id)`

---

### 4.3 activity_checkins（活动签到表）

用户现场签到记录（可上传照片）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 签到ID |
| activity_id | INT | 活动ID |
| user_id | INT | 用户ID |
| checked_in_at | DATETIME | 签到时间 |
| photo_url | VARCHAR(512) | 签到照片 URL |

**约束**：`UNIQUE (activity_id, user_id)`

---

### 4.4 activity_meet_reviews（活动见面评价表）

活动结束后参与者互相评价。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 评价ID |
| activity_id | INT | 活动ID |
| from_user_id | INT | 评价者 |
| to_user_id | INT | 被评价者 |
| met | BOOL | 是否见面 |
| tags | JSON | 评价标签 |
| comment | VARCHAR(50) | 评价内容 |
| created_at | DATETIME | 创建时间 |

**约束**：`UNIQUE (activity_id, from_user_id, to_user_id)`

---

### 4.5 activity_media_audits（活动图片审核表）

活动图片的人工/机审记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 审核ID |
| activity_id | INT | 活动ID |
| user_id | INT | 提交者 |
| status | VARCHAR(16) DEFAULT 'pending' | 审核状态 |
| image_urls | JSON | 待审核图片 URL 数组 |
| trace_entries | JSON | 审核轨迹 |
| reject_index | INT | 被拒绝的图片索引 |
| created_at / updated_at | DATETIME | 时间戳 |

---

## 5. 增长与信任体系

### 5.1 referral_codes（邀请码表）

用户邀请码，一人一码。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| user_id | INT UNIQUE | 用户ID |
| code | VARCHAR(8) UNIQUE | 邀请码 |
| created_at | DATETIME | 创建时间 |

---

### 5.2 referral_bindings（邀请绑定表）

邀请关系绑定，跟踪邀请状态。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| inviter_id | INT | 邀请者 |
| invitee_id | INT UNIQUE | 被邀请者 |
| code | VARCHAR(8) | 使用的邀请码 |
| status | VARCHAR(16) DEFAULT 'pending' | 绑定状态 |
| qualified_action | VARCHAR(32) | 达标动作 |
| qualified_at | DATETIME | 达标时间 |
| reward_granted_at | DATETIME | 奖励发放时间 |
| created_at | DATETIME | 创建时间 |

---

### 5.3 user_entitlements（用户权益表）

用户获得的权益（如置顶次数、会员时长）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 权益ID |
| user_id | INT | 用户ID |
| entitlement_type | VARCHAR(32) | 权益类型 |
| starts_at | DATETIME | 生效时间 |
| expires_at | DATETIME | 过期时间 |
| pin_quota_remaining | INT DEFAULT 0 | 剩余配额 |
| source | VARCHAR(32) | 来源 |
| source_ref_id | INT | 来源引用ID |
| created_at | DATETIME | 创建时间 |

**索引**：`ix_user_entitlements_user_expires` (user_id, expires_at)

---

### 5.4 user_badges（用户徽章表）

用户获得的徽章。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| user_id | INT | 用户ID |
| badge_id | VARCHAR(32) | 徽章ID |
| granted_at | DATETIME | 获得时间 |
| visible | BOOL DEFAULT 1 | 是否展示 |

**约束**：`UNIQUE (user_id, badge_id)`

---

### 5.5 user_trust_profiles（用户信任档案表）

用户信任分数与等级汇总。

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | INT PK | 用户ID |
| trust_score | INT DEFAULT 500 | 信任分数 |
| trust_level | VARCHAR(32) DEFAULT 'basic' | 信任等级 |
| meet_count | INT DEFAULT 0 | 见面次数 |
| show_meet_count | BOOL DEFAULT 1 | 是否展示见面次数 |
| photo_verified | BOOL DEFAULT 0 | 是否真人认证 |
| updated_at | DATETIME | 更新时间 |

---

### 5.6 trust_score_record（信任分变动记录表）

信任分数的每次变动流水。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| user_id | INT | 用户ID |
| `change` | INT | 变动值（正增负减） |
| trust_score_before | INT | 变动前分数 |
| trust_score_after | INT | 变动后分数 |
| reason | VARCHAR(64) | 变动原因 |
| reason_detail | VARCHAR(255) | 详细说明 |
| ref_type | VARCHAR(32) | 关联业务类型 |
| ref_id | INT | 关联业务ID |
| created_at | DATETIME | 创建时间 |

**索引**：
- `ix_trust_score_record_user_id` (user_id)
- `ix_trust_score_record_user_created` (user_id, created_at)

---

### 5.7 user_levels（用户等级表）

用户积分等级汇总。

| 字段 | 类型 | 说明 |
|------|------|------|
| user_id | INT PK | 用户ID |
| total_points | INT DEFAULT 0 | 总积分 |
| level_code | VARCHAR(32) DEFAULT 'recruit' | 等级代码 |
| level_name | VARCHAR(64) DEFAULT '新兵' | 等级名称 |
| updated_at | DATETIME | 更新时间 |

**索引**：`ix_user_levels_total_points` (total_points)

---

### 5.8 point_record（积分变动记录表）

积分的每次变动流水。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| user_id | INT | 用户ID |
| points | INT | 变动积分（正增负减） |
| points_before | INT | 变动前积分 |
| points_after | INT | 变动后积分 |
| reason | VARCHAR(64) | 变动原因 |
| reason_detail | VARCHAR(255) | 详细说明 |
| ref_type | VARCHAR(32) | 关联业务类型 |
| ref_id | INT | 关联业务ID |
| created_at | DATETIME | 创建时间 |

**索引**：
- `ix_point_record_user_id` (user_id)
- `ix_point_record_user_created` (user_id, created_at)

---

### 5.9 photo_verifications（真人认证表）

用户提交的真人认证照片审核。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| user_id | INT | 用户ID |
| selfie_url | VARCHAR(512) | 自拍照 URL |
| status | VARCHAR(16) DEFAULT 'pending' | 审核状态 |
| reject_reason | VARCHAR(256) | 拒绝原因 |
| reviewer_id | INT | 审核人ID |
| submitted_at | DATETIME | 提交时间 |
| reviewed_at | DATETIME | 审核时间 |

**索引**：`ix_photo_verifications_user_status` (user_id, status)

---

### 5.10 user_safety_acks（安全须知确认表）

用户确认安全须知的记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| user_id | INT | 用户ID |
| ack_type | VARCHAR(32) | 确认类型 |
| ack_at | DATETIME | 确认时间 |

**约束**：`UNIQUE (user_id, ack_type)`

---

### 5.11 activity_exposure_boosts（活动曝光加速表）

活动曝光加权记录（如付费置顶）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| activity_id | INT | 活动ID |
| user_id | INT | 操作用户 |
| boost_type | VARCHAR(32) | 加速类型 |
| weight | INT DEFAULT 50 | 权重 |
| starts_at | DATETIME | 生效时间 |
| ends_at | DATETIME | 结束时间 |
| created_at | DATETIME | 创建时间 |

**索引**：`ix_activity_exposure_boosts_act_ends` (activity_id, ends_at)

---

## 6. 内容社区

### 6.1 posts（帖子表）

城市广场/活动动态帖子。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 帖子ID |
| user_id | INT | 发帖用户 |
| post_kind | VARCHAR(16) DEFAULT 'city' | 帖子类型：city / activity |
| city_code | VARCHAR(16) | 城市代码 |
| activity_id | INT NULL | 关联活动ID |
| content | TEXT | 帖子内容 |
| images | JSON | 图片 URL 数组 |
| location_name | VARCHAR(128) | 地点名称 |
| lat / lng | NUMERIC(10,7) | 经纬度 |
| topic_tags | JSON | 话题标签 |
| visibility | VARCHAR(16) DEFAULT 'city_public' | 可见性 |
| status | VARCHAR(16) DEFAULT 'published' | 状态 |
| like_count | INT DEFAULT 0 | 点赞计数（冗余） |
| comment_count | INT DEFAULT 0 | 评论计数（冗余） |
| created_at / updated_at | DATETIME | 时间戳 |

**索引**：
- `ix_posts_city_created` (city_code, created_at)
- `ix_posts_user_id` (user_id)
- `ix_posts_activity_id` (activity_id)
- `ix_posts_kind_status` (post_kind, status)

---

### 6.2 post_likes（帖子点赞表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| post_id | INT | 帖子ID |
| user_id | INT | 点赞用户 |
| created_at | DATETIME | 创建时间 |

**约束**：`UNIQUE (post_id, user_id)`

---

### 6.3 post_comments（帖子评论表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 评论ID |
| post_id | INT | 帖子ID |
| user_id | INT | 评论用户 |
| content | VARCHAR(500) | 评论内容 |
| created_at | DATETIME | 创建时间 |

---

### 6.4 user_follows（用户关注表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT PK | 记录ID |
| follower_id | INT | 关注者 |
| followee_id | INT | 被关注者 |
| created_at | DATETIME | 创建时间 |

**约束**：`UNIQUE (follower_id, followee_id)`

---

## 7. 城市群组管理

### 7.1 city_group_hosts（城市群主表）

城市大群的群主/管理员。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| city_code | VARCHAR(32) | 城市代码 |
| user_id | BIGINT | 用户ID |
| role | VARCHAR(16) | 角色（host/admin） |
| status | VARCHAR(16) DEFAULT 'active' | 状态 |
| appointed_by | BIGINT | 任命者 |
| appointed_at | DATETIME | 任命时间 |
| resigned_at | DATETIME | 离职时间 |
| welcome_text | VARCHAR(500) | 欢迎语 |
| announcement | VARCHAR(1000) | 公告 |
| announcement_updated_at | DATETIME | 公告更新时间 |
| last_active_at | DATETIME | 最后活跃时间 |

**索引**：`ix_city_group_hosts_city_status_role` (city_code, status, role)

---

### 7.2 city_group_host_applications（群主申请表）

用户申请成为城市群主的记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 申请ID |
| city_code | VARCHAR(32) | 城市代码 |
| user_id | BIGINT | 申请用户 |
| application_type | VARCHAR(16) | 申请类型 |
| status | VARCHAR(16) DEFAULT 'pending' | 状态 |
| intro_text | VARCHAR(500) | 自我介绍 |
| nominator_user_id | BIGINT | 推荐人 |
| reviewer_admin_id | BIGINT | 审核管理员 |
| review_note | VARCHAR(256) | 审核备注 |
| created_at | DATETIME | 创建时间 |
| reviewed_at | DATETIME | 审核时间 |

**索引**：
- `ix_city_group_host_applications_city_status` (city_code, status)
- `ix_city_group_host_applications_user` (user_id, status)

---

### 7.3 city_group_host_actions（群主操作日志表）

群主管理操作记录（禁言、删消息等）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| host_id | BIGINT | 群主记录ID |
| city_code | VARCHAR(32) | 城市代码 |
| actor_user_id | BIGINT | 操作者用户ID |
| action | VARCHAR(32) | 操作类型 |
| target_message_id | BIGINT | 目标消息ID |
| target_user_id | BIGINT | 目标用户ID |
| detail | VARCHAR(500) | 操作详情 |
| created_at | DATETIME | 创建时间 |

**索引**：
- `ix_city_group_host_actions_city_code` (city_code)
- `ix_city_group_host_actions_host_id` (host_id)
- `ix_city_group_host_actions_created_at` (created_at)

---

### 7.4 city_group_mutes（群禁言表）

群主对用户的禁言记录。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| city_code | VARCHAR(32) | 城市代码 |
| user_id | BIGINT | 被禁言用户 |
| muted_by_host_id | BIGINT | 执行禁言的群主 |
| muted_until | DATETIME | 禁言截止时间 |
| created_at | DATETIME | 创建时间 |

**索引**：`ix_city_group_mutes_city_user` (city_code, user_id)

---

## 8. 支付与订单

### 8.1 wm_pay_orders（支付订单表）

发布活动等的支付订单（支持微信官方 APIv3 和云购）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 订单ID |
| user_id | BIGINT | 用户ID |
| qr_id | VARCHAR(64) | 二维码ID |
| product | VARCHAR(32) DEFAULT 'publish' | 产品类型 |
| out_trade_no | VARCHAR(64) UNIQUE | 商户订单号 |
| status | VARCHAR(16) DEFAULT 'pending' | 订单状态 |
| channel | VARCHAR(16) DEFAULT 'native' | 支付渠道 |
| pay_provider | VARCHAR(16) DEFAULT 'wechat' | 支付通道：wechat / yungou |
| pay_code_url | VARCHAR(512) | 支付二维码 URL |
| platform_order_no | VARCHAR(64) | 平台订单号 |
| charge_id | VARCHAR(64) | 收费ID |
| money | VARCHAR(16) DEFAULT '1.00' | 金额 |
| attach | VARCHAR(256) | 附加数据 |
| expires_at | DATETIME | 过期时间 |
| paid_at | DATETIME | 支付时间 |
| created_at / updated_at | DATETIME | 时间戳 |

**索引**：
- `idx_wm_pay_orders_user_qr` (user_id, qr_id, product)
- `idx_wm_pay_orders_status_exp` (status, expires_at)

---

## 9. 举报与反馈

### 9.1 reports（举报表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 举报ID |
| reporter_id | BIGINT | 举报者 |
| target_type | VARCHAR(16) | 举报目标类型 |
| target_id | VARCHAR(64) | 举报目标ID |
| activity_id | BIGINT | 关联活动ID |
| reason_code | VARCHAR(32) | 举报原因代码 |
| detail | TEXT | 详细描述 |
| status | VARCHAR(16) DEFAULT 'pending' | 处理状态 |
| handled_action | VARCHAR(32) | 处理动作 |
| handler_admin_id | BIGINT | 处理管理员 |
| handled_at | DATETIME | 处理时间 |
| created_at | DATETIME | 创建时间 |

**索引**：`idx_reports_status_created` (status, created_at)

---

### 9.2 user_feedbacks（用户反馈表）

用户意见与建议（运营后台可读）。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK FK→users | 反馈ID |
| user_id | BIGINT | 用户ID |
| scene | VARCHAR(32) | 反馈场景 |
| description | TEXT | 问题描述 |
| expectation | VARCHAR(500) DEFAULT '' | 期望改进 |
| contact_willing | BOOL DEFAULT 0 | 是否愿意联系 |
| contact_note | VARCHAR(160) DEFAULT '' | 联系方式备注 |
| platform | VARCHAR(16) DEFAULT 'mp-weixin' | 平台 |
| app_version | VARCHAR(32) DEFAULT '' | App 版本 |
| status | VARCHAR(16) DEFAULT 'new' | 状态 |
| created_at | DATETIME | 创建时间 |

**索引**：
- `idx_user_feedbacks_user` (user_id)
- `idx_user_feedbacks_scene` (scene)
- `idx_user_feedbacks_status` (status)
- `idx_user_feedbacks_created` (created_at)

---

### 9.3 user_blocks（用户拉黑表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 记录ID |
| blocker_id | BIGINT | 拉黑者 |
| blocked_id | BIGINT | 被拉黑者 |
| created_at | DATETIME | 创建时间 |

**约束**：`UNIQUE (blocker_id, blocked_id)`

---

### 9.4 notifications（通知表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK | 通知ID |
| user_id | BIGINT | 接收用户 |
| type | VARCHAR(32) | 通知类型 |
| title | VARCHAR(64) | 标题 |
| body | TEXT | 内容 |
| payload_json | JSON | 附加数据 |
| read_at | DATETIME | 已读时间 |
| created_at | DATETIME | 创建时间 |

**索引**：
- `idx_notifications_user_read_created` (user_id, read_at, created_at)
- `idx_notifications_user_read_id` (user_id, read_at, id)

---

### 9.5 place_activity_alerts（地点活动订阅表）

用户订阅某城市/分类的新活动通知。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT PK FK→users | 订阅ID |
| user_id | BIGINT | 用户ID（ON DELETE CASCADE） |
| city_code | VARCHAR(16) | 城市代码 |
| place_label | VARCHAR(128) | 地点标签 |
| category_id | VARCHAR(32) DEFAULT '' | 分类ID |
| date_range | VARCHAR(16) DEFAULT 'all' | 日期范围 |
| status | VARCHAR(16) DEFAULT 'active' | 状态 |
| created_at / updated_at | DATETIME | 时间戳 |

**约束**：`UNIQUE (user_id, city_code, category_id, date_range)`

**索引**：
- `idx_place_alerts_user` (user_id)
- `idx_place_alerts_city` (city_code)

---

## 附录：表统计

| 类别 | 表数量 | 表名 |
|------|--------|------|
| 核心业务 | 3 | users, activities, activity_enrollments |
| 用户认证 | 1 | user_verifications |
| 私信系统 | 5 | dm_threads, dm_requests, direct_messages, dm_thread_reads, dm_thread_removals |
| 活动互动 | 5 | activity_messages, user_chat_reads, activity_checkins, activity_meet_reviews, activity_media_audits |
| 增长与信任 | 11 | referral_codes, referral_bindings, user_entitlements, user_badges, user_trust_profiles, trust_score_record, user_levels, point_record, photo_verifications, user_safety_acks, activity_exposure_boosts |
| 内容社区 | 4 | posts, post_likes, post_comments, user_follows |
| 城市群组 | 4 | city_group_hosts, city_group_host_applications, city_group_host_actions, city_group_mutes |
| 支付与订单 | 1 | wm_pay_orders |
| 举报与反馈 | 5 | reports, user_feedbacks, user_blocks, notifications, place_activity_alerts |
| **合计** | **39** | |

---

## 附录：高频查询索引策略

| 场景 | 索引 | 说明 |
|------|------|------|
| 同城活动列表 | (city_code, activity_status, start_at) | 城市+状态+时间复合筛选 |
| 活动参与者 | (activity_id, status) | 按活动查报名列表 |
| 我的报名 | (user_id, status, activity_id) | 用户视角查已报名活动 |
| 私信请求列表 | (to_user_id, status) | 我的私信请求 |
| 帖子 Feed | (city_code, created_at) | 同城广场按时间排序 |
| 通知列表 | (user_id, read_at, created_at) | 未读通知排序 |
| 群聊消息分页 | (activity_id, id) | 游标分页 |
| 过期订单清理 | (status, expires_at) | 批量关闭过期订单 |

---

## 附录：外键关系

| 子表 | 父表 | 关系 | ON DELETE |
|------|------|------|-----------|
| dm_requests | dm_threads | thread_id → id | SET NULL |
| direct_messages | dm_threads | thread_id → id | CASCADE |
| dm_thread_reads | dm_threads | thread_id → id | CASCADE |
| dm_thread_removals | dm_threads | thread_id → id | CASCADE |
| place_activity_alerts | users | user_id → id | CASCADE |
| user_feedbacks | users | user_id → id | CASCADE |

> 注：大部分业务关联未建外键约束，由应用层保证一致性。
