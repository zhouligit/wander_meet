-- ============================================================
-- WanderMeet (出门晃晃) 数据库初始化脚本 — 干净版
-- 基于 SQLAlchemy Model 定义生成，每张表直接 CREATE 最终态
-- 目标数据库: MySQL 8.0+
-- 字符集: utf8mb4
-- 生成时间: 2026-07-30
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- -----------------------------------------------------------
-- 1. users — 用户主表
-- -----------------------------------------------------------
CREATE TABLE users (
    id                          BIGINT          NOT NULL AUTO_INCREMENT,
    phone                       VARCHAR(20)     NULL,
    phone_hash                  VARCHAR(64)     NOT NULL,
    mp_openid                   VARCHAR(64)     NULL     COMMENT '微信小程序 openid',
    mp_unionid                  VARCHAR(64)     NULL,
    dy_openid                   VARCHAR(64)     NULL     COMMENT '抖音小程序 openid',
    email                       VARCHAR(254)    NULL,
    password_hash               VARCHAR(255)    NULL,
    nickname                    VARCHAR(32)     NOT NULL,
    gender                      VARCHAR(16)     NULL,
    birth_date                  DATE            NULL,
    avatar_url                  VARCHAR(512)    NULL,
    bio                         TEXT            NULL,
    tags                        JSON            NULL,
    country_code                VARCHAR(8)      NULL,
    traveler_roles              JSON            NULL,
    current_place               VARCHAR(256)    NULL,
    stay_kind                   VARCHAR(32)     NULL,
    stay_end_at                 DATETIME        NULL,
    acquisition_source          VARCHAR(64)     NULL,
    notify_prefs                JSON            NULL,
    show_distance               BOOL            NOT NULL DEFAULT 1,
    onboarding_completed_at     DATETIME        NULL,
    enrollment_identity_name    VARCHAR(32)     NULL     COMMENT '报名实名-姓名',
    enrollment_identity_id_card VARCHAR(32)     NULL     COMMENT '报名实名-身份证',
    status                      VARCHAR(16)     NOT NULL DEFAULT 'active',
    `role`                      VARCHAR(16)     NOT NULL DEFAULT 'user',
    created_at                  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_users_phone_hash  (phone_hash),
    UNIQUE KEY uniq_users_mp_openid   (mp_openid),
    UNIQUE KEY uniq_users_dy_openid   (dy_openid),
    UNIQUE KEY uniq_users_email       (email),
    INDEX idx_users_phone             (phone),
    INDEX idx_users_mp_unionid        (mp_unionid)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户主表';

-- -----------------------------------------------------------
-- 2. activities — 活动表
-- -----------------------------------------------------------
CREATE TABLE activities (
    id                          BIGINT          NOT NULL AUTO_INCREMENT,
    activity_kind               VARCHAR(20)     NOT NULL DEFAULT 'event'     COMMENT 'event | city_hall',
    city_hall_province_code     VARCHAR(8)      NULL,
    city_hall_sort_key          VARCHAR(64)     NULL,
    city_hall_city_code         VARCHAR(32)     NULL,
    organizer_id                BIGINT          NOT NULL,
    title                       VARCHAR(80)     NOT NULL,
    description                 TEXT            NOT NULL,
    category_id                 VARCHAR(32)     NOT NULL,
    category_label              VARCHAR(32)     NULL     COMMENT 'category_id=other 时的自定义主题',
    sub_category_id             VARCHAR(32)     NULL,
    city_code                   VARCHAR(16)     NOT NULL,
    location_name               VARCHAR(128)    NOT NULL,
    address_detail              VARCHAR(256)    NULL,
    lat                         NUMERIC(10,7)   NOT NULL,
    lng                         NUMERIC(10,7)   NOT NULL,
    start_at                    DATETIME        NOT NULL,
    end_at                      DATETIME        NULL,
    ended_at                    DATETIME        NULL     COMMENT '实际结束/取消时刻（冗余，便于 past 排序）',
    max_members                 INTEGER         NOT NULL,
    fee_type                    VARCHAR(16)     NOT NULL DEFAULT 'free',
    fee_amount_cents            INTEGER         NULL,
    activity_status             VARCHAR(24)     NOT NULL DEFAULT 'published',
    cover_image_url             VARCHAR(512)    NULL,
    images                      JSON            NULL,
    images_audit_status         VARCHAR(16)     NOT NULL DEFAULT 'none'    COMMENT 'none|pending|pass|reject',
    images_audit_updated_at     DATETIME        NULL,
    guide_sections              JSON            NULL     COMMENT '活动说明页章节',
    require_enrollment_identity BOOL            NOT NULL DEFAULT 0,
    is_pinned                   BOOL            NOT NULL DEFAULT 0 COMMENT '是否置顶',
    pinned_until                DATETIME        NULL     COMMENT '置顶截止时间',
    created_at                  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at                  DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_activities_city_hall_city_code (city_hall_city_code),
    INDEX idx_activities_city_code               (city_code),
    INDEX idx_activities_title                   (title),
    INDEX idx_activities_category_id             (category_id),
    INDEX idx_activities_start_at                (start_at),
    INDEX idx_activities_activity_status         (activity_status),
    INDEX idx_activities_organizer_id            (organizer_id),
    INDEX idx_activities_city_hall_province      (city_hall_province_code),
    INDEX idx_activities_images_audit_status     (images_audit_status),
    INDEX idx_activities_sub_category_id         (sub_category_id),
    INDEX idx_activities_ended_at                (ended_at),
    INDEX idx_activities_organizer_ended         (organizer_id, ended_at),
    -- 复合索引：高频查询场景
    INDEX idx_activities_status_start            (activity_status, start_at),
    INDEX idx_activities_city_status_start        (city_code, activity_status, start_at),
    INDEX idx_activities_city_status_updated     (city_code, activity_status, updated_at),
    INDEX idx_activities_lat_lng                 (lat, lng),
    INDEX idx_activities_kind_status_end_start   (activity_kind, activity_status, end_at, start_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动表';

-- -----------------------------------------------------------
-- 3. activity_enrollments — 活动报名
-- -----------------------------------------------------------
CREATE TABLE activity_enrollments (
    id                  BIGINT          NOT NULL AUTO_INCREMENT,
    activity_id         BIGINT          NOT NULL,
    user_id             BIGINT          NOT NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'joined',
    participant_name    VARCHAR(32)     NULL     COMMENT '实名-姓名',
    id_card_number      VARCHAR(32)     NULL     COMMENT '实名-身份证',
    participant_phone   VARCHAR(20)     NULL     COMMENT '实名-手机号',
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_activity_user (activity_id, user_id),
    INDEX idx_activity_enrollments_activity_status     (activity_id, status),
    INDEX idx_activity_enrollments_user_status_activity (user_id, status, activity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动报名';

-- -----------------------------------------------------------
-- 4. activity_messages — 活动群聊消息（支持软删除）
-- -----------------------------------------------------------
CREATE TABLE activity_messages (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    activity_id     BIGINT          NOT NULL,
    sender_id       BIGINT          NOT NULL,
    msg_type        VARCHAR(16)     NOT NULL DEFAULT 'text',
    text_content    TEXT            NULL,
    image_url       VARCHAR(512)    NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at      DATETIME        NULL     COMMENT '软删除时间',
    PRIMARY KEY (id),
    INDEX idx_activity_messages_activity_created (activity_id, created_at),
    INDEX idx_activity_messages_activity_id_id   (activity_id, id),
    INDEX ix_activity_messages_deleted_at         (deleted_at),
    INDEX idx_activity_messages_sender            (sender_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动群聊消息（支持软删除）';

-- -----------------------------------------------------------
-- 5. dm_threads — 私信会话
-- -----------------------------------------------------------
CREATE TABLE dm_threads (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_low_id     BIGINT          NOT NULL,
    user_high_id    BIGINT          NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_dm_threads_pair (user_low_id, user_high_id),
    INDEX idx_dm_threads_low  (user_low_id),
    INDEX idx_dm_threads_high (user_high_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='私信会话';

-- -----------------------------------------------------------
-- 6. dm_requests — 私信请求
-- -----------------------------------------------------------
CREATE TABLE dm_requests (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    activity_id     BIGINT          NOT NULL,
    from_user_id    BIGINT          NOT NULL,
    to_user_id      BIGINT          NOT NULL,
    intro_text      VARCHAR(500)    NULL,
    status          VARCHAR(16)     NOT NULL DEFAULT 'pending',
    thread_id       BIGINT          NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    responded_at    DATETIME        NULL,
    PRIMARY KEY (id),
    INDEX idx_dm_requests_to_status   (to_user_id, status),
    INDEX idx_dm_requests_from_status (from_user_id, status),
    INDEX idx_dm_requests_activity    (activity_id),
    CONSTRAINT fk_dm_requests_thread FOREIGN KEY (thread_id) REFERENCES dm_threads(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='私信请求';

-- -----------------------------------------------------------
-- 7. direct_messages — 私信消息
-- -----------------------------------------------------------
CREATE TABLE direct_messages (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    thread_id       BIGINT          NOT NULL,
    sender_id       BIGINT          NOT NULL,
    msg_type        VARCHAR(16)     NOT NULL DEFAULT 'text',
    text_content    TEXT            NULL,
    image_url       VARCHAR(512)    NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_direct_messages_thread_created (thread_id, created_at),
    INDEX idx_direct_messages_thread_id_id   (thread_id, id),
    INDEX idx_direct_messages_sender          (sender_id),
    CONSTRAINT fk_direct_messages_thread FOREIGN KEY (thread_id) REFERENCES dm_threads(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='私信消息';

-- -----------------------------------------------------------
-- 8. dm_thread_reads — 私信已读游标
-- -----------------------------------------------------------
CREATE TABLE dm_thread_reads (
    id                      BIGINT          NOT NULL AUTO_INCREMENT,
    user_id                 BIGINT          NOT NULL,
    thread_id               BIGINT          NOT NULL,
    last_read_message_id    BIGINT          NOT NULL DEFAULT 0,
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_dm_thread_read (user_id, thread_id),
    INDEX idx_dm_thread_reads_user (user_id),
    CONSTRAINT fk_dm_thread_reads_thread FOREIGN KEY (thread_id) REFERENCES dm_threads(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='私信已读游标';

-- -----------------------------------------------------------
-- 9. dm_thread_removals — 私信删除（单方面删好友）
-- -----------------------------------------------------------
CREATE TABLE dm_thread_removals (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL,
    thread_id       BIGINT          NOT NULL,
    removed_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_dm_thread_removal (user_id, thread_id),
    INDEX idx_dm_thread_removals_user (user_id),
    CONSTRAINT fk_dm_thread_removals_thread FOREIGN KEY (thread_id) REFERENCES dm_threads(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='私信删除（单方面删好友）';

-- -----------------------------------------------------------
-- 10. user_verifications — 实名认证
-- -----------------------------------------------------------
CREATE TABLE user_verifications (
    id                  BIGINT          NOT NULL AUTO_INCREMENT,
    user_id             BIGINT          NOT NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'pending',
    real_name           VARCHAR(32)     NULL,
    id_card_number      VARCHAR(32)     NULL,
    face_verify_token   VARCHAR(256)    NULL,
    reject_reason       VARCHAR(512)    NULL,
    submitted_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at         DATETIME        NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_user_verifications_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实名认证';

-- -----------------------------------------------------------
-- 11. reports — 举报
-- -----------------------------------------------------------
CREATE TABLE reports (
    id                  BIGINT          NOT NULL AUTO_INCREMENT,
    reporter_id         BIGINT          NOT NULL,
    target_type         VARCHAR(16)     NOT NULL,
    target_id           VARCHAR(64)     NOT NULL,
    activity_id         BIGINT          NULL,
    reason_code         VARCHAR(32)     NOT NULL,
    detail              TEXT            NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'pending',
    handled_action      VARCHAR(32)     NULL,
    handler_admin_id    BIGINT          NULL,
    handled_at          DATETIME        NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_reports_reporter       (reporter_id),
    INDEX idx_reports_target_type    (target_type),
    INDEX idx_reports_target_id      (target_id),
    INDEX idx_reports_activity       (activity_id),
    INDEX idx_reports_status         (status),
    INDEX idx_reports_status_created (status, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='举报';

-- -----------------------------------------------------------
-- 12. user_blocks — 拉黑关系
-- -----------------------------------------------------------
CREATE TABLE user_blocks (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    blocker_id      BIGINT          NOT NULL,
    blocked_id      BIGINT          NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_user_block (blocker_id, blocked_id),
    INDEX idx_user_blocks_blocker (blocker_id),
    INDEX idx_user_blocks_blocked (blocked_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='拉黑关系';

-- -----------------------------------------------------------
-- 13. notifications — 通知
-- -----------------------------------------------------------
CREATE TABLE notifications (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL,
    type            VARCHAR(32)     NOT NULL,
    title           VARCHAR(64)     NOT NULL,
    body            TEXT            NOT NULL,
    payload_json    JSON            NULL,
    read_at         DATETIME        NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_notifications_user_read_created (user_id, read_at, created_at),
    INDEX idx_notifications_user_read_id      (user_id, read_at, id),
    INDEX idx_notifications_type              (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通知';

-- -----------------------------------------------------------
-- 14. user_chat_reads — 群聊已读游标
-- -----------------------------------------------------------
CREATE TABLE user_chat_reads (
    id                      BIGINT          NOT NULL AUTO_INCREMENT,
    user_id                 BIGINT          NOT NULL,
    activity_id             BIGINT          NOT NULL,
    last_read_message_id    BIGINT          NOT NULL DEFAULT 0,
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_user_chat_read (user_id, activity_id),
    INDEX idx_user_chat_reads_user     (user_id),
    INDEX idx_user_chat_reads_activity (activity_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群聊已读游标';

-- -----------------------------------------------------------
-- 15. place_activity_alerts — 地点活动订阅
-- -----------------------------------------------------------
CREATE TABLE place_activity_alerts (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL,
    city_code       VARCHAR(16)     NOT NULL,
    place_label     VARCHAR(128)    NOT NULL,
    category_id     VARCHAR(32)     NOT NULL DEFAULT '',
    date_range      VARCHAR(16)     NOT NULL DEFAULT 'all',
    status          VARCHAR(16)     NOT NULL DEFAULT 'active',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_place_alerts_user_city_cat_dr (user_id, city_code, category_id, date_range),
    INDEX idx_place_alerts_user (user_id),
    INDEX idx_place_alerts_city (city_code),
    CONSTRAINT fk_place_alerts_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='地点活动订阅';

-- -----------------------------------------------------------
-- 16. user_feedbacks — 用户反馈
-- -----------------------------------------------------------
CREATE TABLE user_feedbacks (
    id                  BIGINT          NOT NULL AUTO_INCREMENT,
    user_id             BIGINT          NOT NULL,
    scene               VARCHAR(32)     NOT NULL,
    description         TEXT            NOT NULL,
    expectation         VARCHAR(500)    NOT NULL DEFAULT '',
    contact_willing     BOOL            NOT NULL DEFAULT 0,
    contact_note        VARCHAR(160)    NOT NULL DEFAULT '',
    platform            VARCHAR(16)     NOT NULL DEFAULT 'mp-weixin',
    app_version         VARCHAR(32)     NOT NULL DEFAULT '',
    status              VARCHAR(16)     NOT NULL DEFAULT 'new',
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_user_feedbacks_user    (user_id),
    INDEX idx_user_feedbacks_scene   (scene),
    INDEX idx_user_feedbacks_status  (status),
    INDEX idx_user_feedbacks_created (created_at),
    CONSTRAINT fk_user_feedbacks_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户反馈';

-- -----------------------------------------------------------
-- 17. posts — 帖子（城市广场 / 活动动态）
-- -----------------------------------------------------------
CREATE TABLE posts (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    user_id         INTEGER         NOT NULL,
    post_kind       VARCHAR(16)     NOT NULL DEFAULT 'city'     COMMENT 'city | activity',
    city_code       VARCHAR(16)     NOT NULL,
    activity_id     INTEGER         NULL,
    content         TEXT            NOT NULL,
    images          JSON            NULL,
    location_name   VARCHAR(128)    NULL,
    lat             NUMERIC(10,7)   NULL,
    lng             NUMERIC(10,7)   NULL,
    topic_tags      JSON            NULL,
    visibility      VARCHAR(16)     NOT NULL DEFAULT 'city_public',
    status          VARCHAR(16)     NOT NULL DEFAULT 'published',
    like_count      INTEGER         NOT NULL DEFAULT 0,
    comment_count   INTEGER         NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_posts_city_created    (city_code, created_at),
    INDEX ix_posts_user_id         (user_id),
    INDEX ix_posts_activity_id     (activity_id),
    INDEX ix_posts_kind_status     (post_kind, status),
    INDEX ix_posts_created_at      (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='帖子（城市广场/活动动态）';

-- -----------------------------------------------------------
-- 18. post_likes — 帖子点赞
-- -----------------------------------------------------------
CREATE TABLE post_likes (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    post_id         INTEGER         NOT NULL,
    user_id         INTEGER         NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_post_likes_post_user (post_id, user_id),
    INDEX ix_post_likes_post_id (post_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='帖子点赞';

-- -----------------------------------------------------------
-- 19. post_comments — 帖子评论
-- -----------------------------------------------------------
CREATE TABLE post_comments (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    post_id         INTEGER         NOT NULL,
    user_id         INTEGER         NOT NULL,
    content         VARCHAR(500)    NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_post_comments_post_id (post_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='帖子评论';

-- -----------------------------------------------------------
-- 20. user_follows — 用户关注
-- -----------------------------------------------------------
CREATE TABLE user_follows (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    follower_id     INTEGER         NOT NULL,
    followee_id     INTEGER         NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_follows_pair (follower_id, followee_id),
    INDEX ix_user_follows_followee (followee_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户关注';

-- -----------------------------------------------------------
-- 21. city_group_hosts — 城市群主
-- -----------------------------------------------------------
CREATE TABLE city_group_hosts (
    id                          BIGINT          NOT NULL AUTO_INCREMENT,
    city_code                   VARCHAR(32)     NOT NULL,
    user_id                     BIGINT          NOT NULL,
    `role`                      VARCHAR(16)     NOT NULL,
    status                      VARCHAR(16)     NOT NULL DEFAULT 'active',
    appointed_by                BIGINT          NULL,
    appointed_at                DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resigned_at                 DATETIME        NULL,
    welcome_text                VARCHAR(500)    NULL,
    announcement                VARCHAR(1000)   NULL,
    announcement_updated_at     DATETIME        NULL,
    last_active_at              DATETIME        NULL,
    PRIMARY KEY (id),
    INDEX ix_city_group_hosts_city_code         (city_code),
    INDEX ix_city_group_hosts_user_id           (user_id),
    INDEX ix_city_group_hosts_city_status_role  (city_code, status, `role`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='城市群主';

-- -----------------------------------------------------------
-- 22. city_group_host_applications — 群主申请
-- -----------------------------------------------------------
CREATE TABLE city_group_host_applications (
    id                      BIGINT          NOT NULL AUTO_INCREMENT,
    city_code               VARCHAR(32)     NOT NULL,
    user_id                 BIGINT          NOT NULL,
    application_type        VARCHAR(16)     NOT NULL,
    status                  VARCHAR(16)     NOT NULL DEFAULT 'pending',
    intro_text              VARCHAR(500)    NULL,
    nominator_user_id       BIGINT          NULL,
    reviewer_admin_id       BIGINT          NULL,
    review_note             VARCHAR(256)    NULL,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at             DATETIME        NULL,
    PRIMARY KEY (id),
    INDEX ix_city_group_host_applications_city_status (city_code, status),
    INDEX ix_city_group_host_applications_user        (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群主申请';

-- -----------------------------------------------------------
-- 23. city_group_host_actions — 群主操作日志
-- -----------------------------------------------------------
CREATE TABLE city_group_host_actions (
    id                      BIGINT          NOT NULL AUTO_INCREMENT,
    host_id                 BIGINT          NOT NULL,
    city_code               VARCHAR(32)     NOT NULL,
    actor_user_id           BIGINT          NOT NULL,
    action                  VARCHAR(32)     NOT NULL,
    target_message_id       BIGINT          NULL,
    target_user_id          BIGINT          NULL,
    detail                  VARCHAR(500)    NULL,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_city_group_host_actions_city_code  (city_code),
    INDEX ix_city_group_host_actions_host_id    (host_id),
    INDEX ix_city_group_host_actions_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群主操作日志';

-- -----------------------------------------------------------
-- 24. city_group_mutes — 群禁言
-- -----------------------------------------------------------
CREATE TABLE city_group_mutes (
    id                  BIGINT          NOT NULL AUTO_INCREMENT,
    city_code           VARCHAR(32)     NOT NULL,
    user_id             BIGINT          NOT NULL,
    muted_by_host_id    BIGINT          NOT NULL,
    muted_until         DATETIME        NOT NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_city_group_mutes_city_user (city_code, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='群禁言';

-- -----------------------------------------------------------
-- 25. wm_pay_orders — 支付订单
-- -----------------------------------------------------------
CREATE TABLE wm_pay_orders (
    id                  BIGINT          NOT NULL AUTO_INCREMENT,
    user_id             BIGINT          NOT NULL,
    qr_id               VARCHAR(64)     NOT NULL,
    product             VARCHAR(32)     NOT NULL DEFAULT 'publish',
    out_trade_no        VARCHAR(64)     NOT NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'pending',
    channel             VARCHAR(16)     NOT NULL DEFAULT 'native',
    pay_provider        VARCHAR(16)     NOT NULL DEFAULT 'wechat'    COMMENT 'wechat | yungou',
    pay_code_url        VARCHAR(512)    NULL,
    platform_order_no   VARCHAR(64)     NULL,
    charge_id           VARCHAR(64)     NULL,
    money               VARCHAR(16)     NOT NULL DEFAULT '1.00',
    attach              VARCHAR(256)    NULL,
    expires_at          DATETIME        NOT NULL,
    paid_at             DATETIME        NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_wm_pay_orders_out_trade_no (out_trade_no),
    INDEX idx_wm_pay_orders_user_qr   (user_id, qr_id, product),
    INDEX idx_wm_pay_orders_status_exp (status, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='支付订单';

-- -----------------------------------------------------------
-- 26. trust_score_record — 信任分变动记录
-- -----------------------------------------------------------
CREATE TABLE trust_score_record (
    id                      INTEGER         NOT NULL AUTO_INCREMENT,
    user_id                 INTEGER         NOT NULL,
    `change`                INTEGER         NOT NULL    COMMENT '变动值（正数增加，负数减少）',
    trust_score_before      INTEGER         NOT NULL    COMMENT '变动前分数',
    trust_score_after       INTEGER         NOT NULL    COMMENT '变动后分数',
    reason                  VARCHAR(64)     NOT NULL    COMMENT '变动原因',
    reason_detail           VARCHAR(255)    NULL        COMMENT '详细说明',
    ref_type                VARCHAR(32)     NULL        COMMENT '关联业务类型',
    ref_id                  INTEGER         NULL        COMMENT '关联业务ID',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_trust_score_record_user_id      (user_id),
    INDEX ix_trust_score_record_user_created  (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信誉分变动记录';

-- -----------------------------------------------------------
-- 27. user_levels — 用户等级
-- -----------------------------------------------------------
CREATE TABLE user_levels (
    user_id         INTEGER         NOT NULL,
    total_points    INTEGER         NOT NULL DEFAULT 0  COMMENT '总积分',
    level_code      VARCHAR(32)     NOT NULL DEFAULT 'recruit' COMMENT '等级代码',
    level_name      VARCHAR(64)     NOT NULL DEFAULT '新兵'    COMMENT '等级名称',
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    INDEX ix_user_levels_total_points (total_points)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户等级';

-- -----------------------------------------------------------
-- 28. point_record — 积分变动记录
-- -----------------------------------------------------------
CREATE TABLE point_record (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         INTEGER         NOT NULL,
    points          INTEGER         NOT NULL    COMMENT '变动积分（正数增加，负数减少）',
    points_before   INTEGER         NOT NULL    COMMENT '变动前积分',
    points_after    INTEGER         NOT NULL    COMMENT '变动后积分',
    reason          VARCHAR(64)     NOT NULL    COMMENT '变动原因',
    reason_detail   VARCHAR(255)    NULL        COMMENT '详细说明',
    ref_type        VARCHAR(32)     NULL        COMMENT '关联业务类型',
    ref_id          INTEGER         NULL        COMMENT '关联业务ID',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_point_record_user_id      (user_id),
    INDEX ix_point_record_user_created  (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='积分变动记录';

-- -----------------------------------------------------------
-- 29. activity_media_audits — 活动图片审核
-- -----------------------------------------------------------
CREATE TABLE activity_media_audits (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    activity_id     INTEGER         NOT NULL,
    user_id         INTEGER         NOT NULL,
    status          VARCHAR(16)     NOT NULL DEFAULT 'pending',
    image_urls      JSON            NOT NULL,
    trace_entries   JSON            NULL,
    reject_index    INTEGER         NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_activity_media_audits_activity_id (activity_id),
    INDEX ix_activity_media_audits_status      (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动图片审核';

-- -----------------------------------------------------------
-- 30. activity_checkins — 活动签到
-- -----------------------------------------------------------
CREATE TABLE activity_checkins (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    activity_id     INTEGER         NOT NULL,
    user_id         INTEGER         NOT NULL,
    checked_in_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    photo_url       VARCHAR(512)    NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_activity_checkins_act_user (activity_id, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动签到';

-- -----------------------------------------------------------
-- 31. activity_meet_reviews — 活动见面评价
-- -----------------------------------------------------------
CREATE TABLE activity_meet_reviews (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    activity_id     INTEGER         NOT NULL,
    from_user_id    INTEGER         NOT NULL,
    to_user_id      INTEGER         NOT NULL,
    met             BOOL            NOT NULL,
    tags            JSON            NULL,
    comment         VARCHAR(50)     NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_activity_meet_reviews_triple (activity_id, from_user_id, to_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动见面评价';

-- -----------------------------------------------------------
-- 32. activity_exposure_boosts — 活动曝光加速
-- -----------------------------------------------------------
CREATE TABLE activity_exposure_boosts (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    activity_id     INTEGER         NOT NULL,
    user_id         INTEGER         NOT NULL,
    boost_type      VARCHAR(32)     NOT NULL,
    weight          INTEGER         NOT NULL DEFAULT 50,
    starts_at       DATETIME        NOT NULL,
    ends_at         DATETIME        NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_activity_exposure_boosts_act_ends (activity_id, ends_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动曝光加速';

-- -----------------------------------------------------------
-- 33. user_trust_profiles — 用户信任档案
-- -----------------------------------------------------------
CREATE TABLE user_trust_profiles (
    user_id         INTEGER         NOT NULL,
    trust_score     INTEGER         NOT NULL DEFAULT 500,
    trust_level     VARCHAR(32)     NOT NULL DEFAULT 'basic',
    meet_count      INTEGER         NOT NULL DEFAULT 0,
    show_meet_count BOOL            NOT NULL DEFAULT 1,
    photo_verified  BOOL            NOT NULL DEFAULT 0,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信任档案';

-- -----------------------------------------------------------
-- 34. user_safety_acks — 安全须知确认
-- -----------------------------------------------------------
CREATE TABLE user_safety_acks (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    user_id         INTEGER         NOT NULL,
    ack_type        VARCHAR(32)     NOT NULL,
    ack_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_safety_acks_user_type (user_id, ack_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='安全须知确认';

-- -----------------------------------------------------------
-- 35. referral_codes — 邀请码
-- -----------------------------------------------------------
CREATE TABLE referral_codes (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    user_id         INTEGER         NOT NULL,
    code            VARCHAR(8)      NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_referral_codes_user_id (user_id),
    UNIQUE KEY uq_referral_codes_code    (code),
    INDEX ix_referral_codes_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邀请码';

-- -----------------------------------------------------------
-- 36. referral_bindings — 邀请绑定
-- -----------------------------------------------------------
CREATE TABLE referral_bindings (
    id                  INTEGER         NOT NULL AUTO_INCREMENT,
    inviter_id          INTEGER         NOT NULL,
    invitee_id          INTEGER         NOT NULL,
    code                VARCHAR(8)      NOT NULL,
    status              VARCHAR(16)     NOT NULL DEFAULT 'pending',
    qualified_action    VARCHAR(32)     NULL,
    qualified_at        DATETIME        NULL,
    reward_granted_at   DATETIME        NULL,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_referral_bindings_invitee_id (invitee_id),
    INDEX ix_referral_bindings_inviter_status (inviter_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邀请绑定';

-- -----------------------------------------------------------
-- 37. user_entitlements — 用户权益
-- -----------------------------------------------------------
CREATE TABLE user_entitlements (
    id                      INTEGER         NOT NULL AUTO_INCREMENT,
    user_id                 INTEGER         NOT NULL,
    entitlement_type        VARCHAR(32)     NOT NULL,
    starts_at               DATETIME        NOT NULL,
    expires_at              DATETIME        NOT NULL,
    pin_quota_remaining     INTEGER         NOT NULL DEFAULT 0,
    source                  VARCHAR(32)     NOT NULL,
    source_ref_id           INTEGER         NULL,
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_user_entitlements_user_expires (user_id, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户权益';

-- -----------------------------------------------------------
-- 38. user_badges — 用户徽章
-- -----------------------------------------------------------
CREATE TABLE user_badges (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    user_id         INTEGER         NOT NULL,
    badge_id        VARCHAR(32)     NOT NULL,
    granted_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    visible         BOOL            NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    UNIQUE KEY uq_user_badges_user_badge (user_id, badge_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户徽章';

-- -----------------------------------------------------------
-- 39. photo_verifications — 真人认证
-- -----------------------------------------------------------
CREATE TABLE photo_verifications (
    id              INTEGER         NOT NULL AUTO_INCREMENT,
    user_id         INTEGER         NOT NULL,
    selfie_url      VARCHAR(512)    NOT NULL,
    status          VARCHAR(16)     NOT NULL DEFAULT 'pending',
    reject_reason   VARCHAR(256)    NULL,
    reviewer_id     INTEGER         NULL,
    submitted_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at     DATETIME        NULL,
    PRIMARY KEY (id),
    INDEX ix_photo_verifications_user_status (user_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='真人认证';


-- -----------------------------------------------------------
-- 40. wander_coin_wallets — 晃晃币钱包
-- -----------------------------------------------------------
CREATE TABLE wander_coin_wallets (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL COMMENT '用户ID',
    balance         BIGINT          NOT NULL DEFAULT 0 COMMENT '当前余额',
    total_earned    BIGINT          NOT NULL DEFAULT 0 COMMENT '累计获得',
    total_spent     BIGINT          NOT NULL DEFAULT 0 COMMENT '累计消费',
    frozen_amount   BIGINT          NOT NULL DEFAULT 0 COMMENT '冻结金额（如置顶中）',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uniq_wander_coin_wallets_user_id (user_id),
    CONSTRAINT fk_wander_coin_wallets_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='晃晃币钱包';

-- -----------------------------------------------------------
-- 41. wander_coin_transactions — 晃晃币交易流水
-- -----------------------------------------------------------
CREATE TABLE wander_coin_transactions (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL COMMENT '用户ID',
    amount          BIGINT          NOT NULL COMMENT '变动金额（正数=收入，负数=支出）',
    balance_after   BIGINT          NOT NULL COMMENT '交易后余额',
    tx_type         VARCHAR(32)     NOT NULL COMMENT '交易类型',
    ref_type        VARCHAR(32)     NULL     COMMENT '关联业务类型',
    ref_id          BIGINT          NULL     COMMENT '关联业务ID',
    remark          VARCHAR(255)    NULL     COMMENT '备注',
    expire_at       DATETIME        NULL     COMMENT '本笔过期时间（获得时设置）',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_wander_coin_tx_user_time (user_id, created_at),
    INDEX idx_wander_coin_tx_type      (tx_type, created_at),
    INDEX idx_wander_coin_tx_expire    (expire_at),
    CONSTRAINT fk_wander_coin_tx_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='晃晃币交易流水';

-- -----------------------------------------------------------
-- 42. trust_score_appeals — 信誉分申诉
-- -----------------------------------------------------------
CREATE TABLE trust_score_appeals (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL COMMENT '申诉用户ID',
    record_id       BIGINT          NOT NULL COMMENT '关联的信誉分变动记录ID',
    appeal_reason   TEXT            NOT NULL COMMENT '申诉理由',
    status          VARCHAR(32)     NOT NULL DEFAULT 'pending' COMMENT '申诉状态: pending/rejected/approved',
    reviewer_id     BIGINT          NULL     COMMENT '审核人ID',
    review_comment  TEXT            NULL     COMMENT '审核意见',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at     DATETIME        NULL     COMMENT '审核时间',
    PRIMARY KEY (id),
    INDEX idx_trust_appeals_user_status (user_id, status),
    INDEX idx_trust_appeals_record_id   (record_id),
    CONSTRAINT fk_trust_appeals_user     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_trust_appeals_record   FOREIGN KEY (record_id) REFERENCES trust_score_record(id) ON DELETE CASCADE,
    CONSTRAINT fk_trust_appeals_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信誉分申诉';

-- -----------------------------------------------------------
-- 43. point_appeals — 积分申诉
-- -----------------------------------------------------------
CREATE TABLE point_appeals (
    id              BIGINT          NOT NULL AUTO_INCREMENT,
    user_id         BIGINT          NOT NULL COMMENT '申诉用户ID',
    record_id       BIGINT          NOT NULL COMMENT '关联的积分变动记录ID',
    appeal_reason   TEXT            NOT NULL COMMENT '申诉理由',
    status          VARCHAR(32)     NOT NULL DEFAULT 'pending' COMMENT '申诉状态: pending/rejected/approved',
    reviewer_id     BIGINT          NULL     COMMENT '审核人ID',
    review_comment  TEXT            NULL     COMMENT '审核意见',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at     DATETIME        NULL     COMMENT '审核时间',
    PRIMARY KEY (id),
    INDEX idx_point_appeals_user_status (user_id, status),
    INDEX idx_point_appeals_record_id   (record_id),
    CONSTRAINT fk_point_appeals_user     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_point_appeals_record   FOREIGN KEY (record_id) REFERENCES point_record(id) ON DELETE CASCADE,
    CONSTRAINT fk_point_appeals_reviewer FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='积分申诉';

-- -----------------------------------------------------------
-- alembic_version — 迁移版本跟踪（Alembic 自动生成）
-- -----------------------------------------------------------
CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 标记当前迁移版本
INSERT INTO alembic_version (version_num) VALUES ('wander_coin_appeal');

-- ============================================================
-- 种子数据 (Seed Data)
-- ============================================================

-- -----------------------------------------------------------
-- 系统管理员（城市大群 organizer_id，phone_hash 由
-- hash_phone('_wm_internal_city_hall_system_v1') 生成）
-- -----------------------------------------------------------
INSERT INTO users (
    id, phone, phone_hash, mp_openid, mp_unionid, dy_openid,
    email, password_hash, nickname, gender, birth_date, avatar_url,
    bio, tags, country_code, traveler_roles, current_place,
    stay_kind, stay_end_at, acquisition_source, notify_prefs,
    show_distance, onboarding_completed_at,
    enrollment_identity_name, enrollment_identity_id_card,
    status, `role`, created_at, updated_at
) VALUES (
    1, NULL,
    'eef2ce8c11ca909a0fc26da81f0f3cff54166739d9f6421055831cba19b2cbe9',
    NULL, NULL, NULL, NULL, NULL,
    '系统管理员', NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL,
    0, NOW(),
    NULL, NULL,
    'active', 'admin', NOW(), NOW()
);

-- -----------------------------------------------------------
-- 系统管理员等级初始化
-- -----------------------------------------------------------
INSERT INTO user_levels (user_id, total_points, level_code, level_name, updated_at)
VALUES (1, 0, 'recruit', '新兵', NOW());

-- -----------------------------------------------------------
-- 系统管理员信任档案初始化
-- -----------------------------------------------------------
INSERT INTO user_trust_profiles (user_id, trust_score, trust_level, meet_count, show_meet_count, photo_verified, updated_at)
VALUES (1, 500, 'basic', 0, 0, 0, NOW());

SET FOREIGN_KEY_CHECKS = 1;