-- ============================================================
-- WanderMeet 数据库迁移脚本 - 2026-07-31
-- 包含：信任分等级系统 + 活动置顶功能
-- ============================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. 信任分等级系统表结构
-- ============================================================

-- 1.1 信任分变动记录表
CREATE TABLE IF NOT EXISTS trust_score_record (
    id                      INT             NOT NULL AUTO_INCREMENT,
    user_id                 INT             NOT NULL,
    `change`                INT             NOT NULL COMMENT '变动值（正数增加，负数减少）',
    trust_score_before      INT             NOT NULL COMMENT '变动前分数',
    trust_score_after       INT             NOT NULL COMMENT '变动后分数',
    reason                  VARCHAR(64)     NOT NULL COMMENT '变动原因',
    reason_detail           VARCHAR(255)    NULL     COMMENT '详细说明',
    ref_type                VARCHAR(32)     NULL     COMMENT '关联业务类型',
    ref_id                  INT             NULL     COMMENT '关联业务ID',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_trust_score_record_user_id (user_id),
    INDEX ix_trust_score_record_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='信任分变动记录表';

-- 1.2 用户等级表
CREATE TABLE IF NOT EXISTS user_levels (
    user_id                 INT             NOT NULL,
    total_points            INT             NOT NULL DEFAULT 0 COMMENT '总积分',
    level_code              VARCHAR(32)     NOT NULL DEFAULT 'recruit' COMMENT '等级代码',
    level_name              VARCHAR(64)     NOT NULL DEFAULT '新兵' COMMENT '等级名称',
    updated_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id),
    INDEX ix_user_levels_total_points (total_points)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户等级表';

-- 1.3 积分变动记录表
CREATE TABLE IF NOT EXISTS point_record (
    id                      BIGINT          NOT NULL AUTO_INCREMENT,
    user_id                 INT             NOT NULL,
    points                  INT             NOT NULL COMMENT '变动积分（正数增加，负数减少）',
    points_before           INT             NOT NULL COMMENT '变动前积分',
    points_after            INT             NOT NULL COMMENT '变动后积分',
    reason                  VARCHAR(64)     NOT NULL COMMENT '变动原因',
    reason_detail           VARCHAR(255)    NULL     COMMENT '详细说明',
    ref_type                VARCHAR(32)     NULL     COMMENT '关联业务类型',
    ref_id                  INT             NULL     COMMENT '关联业务ID',
    created_at              DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX ix_point_record_user_id (user_id),
    INDEX ix_point_record_user_created (user_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='积分变动记录表';

-- ============================================================
-- 2. 活动表新增置顶字段（幂等处理）
-- ============================================================

-- 使用存储过程确保幂等性
DROP PROCEDURE IF EXISTS add_activity_pin_columns;

DELIMITER $$
CREATE PROCEDURE add_activity_pin_columns()
BEGIN
    DECLARE col_exists INT DEFAULT 0;
    
    -- 检查 is_pinned 列是否存在
    SELECT COUNT(*) INTO col_exists
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'activities'
      AND COLUMN_NAME = 'is_pinned';
    
    IF col_exists = 0 THEN
        ALTER TABLE activities 
        ADD COLUMN is_pinned TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否置顶' AFTER images_audit_updated_at;
    END IF;
    
    -- 检查 pinned_until 列是否存在
    SELECT COUNT(*) INTO col_exists
    FROM information_schema.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'activities'
      AND COLUMN_NAME = 'pinned_until';
    
    IF col_exists = 0 THEN
        ALTER TABLE activities 
        ADD COLUMN pinned_until DATETIME NULL COMMENT '置顶截止时间' AFTER is_pinned;
    END IF;
    
    -- 检查索引是否存在
    SELECT COUNT(*) INTO col_exists
    FROM information_schema.STATISTICS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'activities'
      AND INDEX_NAME = 'idx_activities_is_pinned';
    
    IF col_exists = 0 THEN
        ALTER TABLE activities ADD INDEX idx_activities_is_pinned (is_pinned);
    END IF;
END$$
DELIMITER ;

CALL add_activity_pin_columns();
DROP PROCEDURE IF EXISTS add_activity_pin_columns;

-- ============================================================
-- 3. Alembic 版本记录
-- ============================================================

-- 创建 Alembic 版本表（如不存在）
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    PRIMARY KEY (version_num)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 更新版本号为最新的 migration revision
INSERT INTO alembic_version (version_num) VALUES ('20260723_0033')
ON DUPLICATE KEY UPDATE version_num = '20260723_0033';

-- ============================================================
-- 4. 验证查询（可选，用于确认变更成功）
-- ============================================================

-- 验证表结构
-- SHOW CREATE TABLE trust_score_record\G
-- SHOW CREATE TABLE user_levels\G
-- SHOW CREATE TABLE point_record\G
-- SHOW COLUMNS FROM activities LIKE '%pin%';
-- SELECT * FROM alembic_version;

-- ============================================================
-- 5. 回滚脚本（如需回滚，请取消注释执行）
-- ============================================================

-- -- 5.1 回滚活动置顶字段
-- ALTER TABLE activities
-- DROP INDEX idx_activities_is_pinned,
-- DROP COLUMN pinned_until,
-- DROP COLUMN is_pinned;

-- -- 5.2 回滚信任分等级系统表
-- DROP TABLE IF EXISTS point_record;
-- DROP TABLE IF EXISTS user_levels;
-- DROP TABLE IF EXISTS trust_score_record;

-- -- 5.3 回滚 Alembic 版本
-- DELETE FROM alembic_version WHERE version_num = '20260723_0033';

SET FOREIGN_KEY_CHECKS = 1;
