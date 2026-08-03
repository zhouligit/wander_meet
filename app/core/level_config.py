"""等级配置和积分规则"""

# 等级阶梯定义：(所需积分, 等级代码, 等级名称)
LEVEL_TIERS = [
    (0, "recruit", "新兵"),
    (100, "private", "列兵"),
    (300, "corporal", "上等兵"),
    (600, "sergeant", "下士"),
    (1000, "staff_sergeant", "中士"),
    (1500, "sergeant_first_class", "上士"),
    (2200, "master_sergeant", "军士长"),
    (3000, "second_lieutenant", "少尉"),
    (4000, "first_lieutenant", "中尉"),
    (5500, "captain", "上尉"),
    (7500, "major", "少校"),
    (10000, "lieutenant_colonel", "中校"),
    (13000, "colonel", "上校"),
    (17000, "brigadier_general", "准将"),
    (22000, "major_general", "少将"),
    (28000, "lieutenant_general", "中将"),
    (35000, "general", "上将"),
]

# 等级权益定义
LEVEL_PRIVILEGES = {
    "recruit": {
        "level_type": "士兵",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"}
        ]
    },
    "private": {
        "level_type": "士兵",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"}
        ]
    },
    "corporal": {
        "level_type": "士兵",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"}
        ]
    },
    "sergeant": {
        "level_type": "士官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority_light", "name": "活动列表轻微优先展示"}
        ]
    },
    "staff_sergeant": {
        "level_type": "士官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"}
        ]
    },
    "sergeant_first_class": {
        "level_type": "士官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"}
        ]
    },
    "master_sergeant": {
        "level_type": "士官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "sergeant_special_badge", "name": "军士长专属徽章"}
        ]
    },
    "second_lieutenant": {
        "level_type": "军官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"}
        ]
    },
    "first_lieutenant": {
        "level_type": "军官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"}
        ]
    },
    "captain": {
        "level_type": "军官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"}
        ]
    },
    "major": {
        "level_type": "军官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"}
        ]
    },
    "lieutenant_colonel": {
        "level_type": "军官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"}
        ]
    },
    "colonel": {
        "level_type": "军官",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"}
        ]
    },
    "brigadier_general": {
        "level_type": "将军",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"},
            {"code": "homepage_recommend", "name": "首页推荐位"}
        ]
    },
    "major_general": {
        "level_type": "将军",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"},
            {"code": "homepage_recommend", "name": "首页推荐位"},
            {"code": "general_badge", "name": "专属将军标识"}
        ]
    },
    "lieutenant_general": {
        "level_type": "将军",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"},
            {"code": "homepage_recommend", "name": "首页推荐位"},
            {"code": "general_badge", "name": "专属将军标识"}
        ]
    },
    "general": {
        "level_type": "将军",
        "privileges": [
            {"code": "basic_function", "name": "基础功能（发布活动、参与活动、评论、私信）"},
            {"code": "activity_priority", "name": "活动列表优先展示"},
            {"code": "sergeant_badge", "name": "专属士官标识"},
            {"code": "no_review_publish", "name": "活动免审核发布"},
            {"code": "officer_badge", "name": "专属军官标识"},
            {"code": "homepage_recommend", "name": "首页推荐位"},
            {"code": "general_badge", "name": "专属将军标识"},
            {"code": "vip_support", "name": "运营专属客服"}
        ]
    },
}

# 积分规则：行为 -> 积分值（对齐 PRD 04-积分等级体系）
POINT_RULES = {
    "publish_activity": 10,        # 发布活动
    "join_activity": 15,           # 参与活动（打卡）
    "referral_register": 30,       # 邀请好友注册
    "referral_first_join": 20,     # 好友首次参加活动
    "post_comment": 3,             # 发布评论
    "receive_good_review": 5,      # 收到好评
    "meet_success": 20,            # 见面成功
    "photo_verify": 50,            # 照片验证通过
    "daily_login": 2,              # 每日登录
    "login_streak_7": 20,          # 连续登录 7 天
    "login_streak_30": 100,        # 连续登录 30 天
    "valid_report": 10,            # 有效举报
}


def get_level_by_points(points: int) -> tuple[str, str]:
    """根据积分获取等级代码和名称"""
    level_code = "recruit"
    level_name = "新兵"
    
    for tier_points, code, name in LEVEL_TIERS:
        if points >= tier_points:
            level_code = code
            level_name = name
        else:
            break
    
    return level_code, level_name


def get_next_level(current_points: int) -> dict | None:
    """获取下一等级信息"""
    current_tier_idx = 0
    
    for i, (tier_points, code, name) in enumerate(LEVEL_TIERS):
        if current_points >= tier_points:
            current_tier_idx = i
        else:
            break
    
    # 已是最高等级
    if current_tier_idx >= len(LEVEL_TIERS) - 1:
        return None
    
    next_tier = LEVEL_TIERS[current_tier_idx + 1]
    current_tier = LEVEL_TIERS[current_tier_idx]
    
    next_points, next_code, next_name = next_tier
    current_tier_points = current_tier[0]
    
    # 计算进度
    points_in_tier = current_points - current_tier_points
    tier_span = next_points - current_tier_points
    progress = points_in_tier / tier_span if tier_span > 0 else 0
    
    return {
        "points_required": next_points,
        "level_code": next_code,
        "level_name": next_name,
        "progress": round(progress, 3),
        "points_needed": next_points - current_points,
    }


def get_user_privileges(level_code: str) -> dict:
    """获取用户当前等级的权益信息"""
    if level_code not in LEVEL_PRIVILEGES:
        level_code = "recruit"
    
    privilege_info = LEVEL_PRIVILEGES[level_code]
    
    # 查找下一等级的权益（用于展示"即将解锁"）
    next_level_privileges = []
    current_idx = None
    for i, (points, code, name) in enumerate(LEVEL_TIERS):
        if code == level_code:
            current_idx = i
            break
    
    if current_idx is not None and current_idx < len(LEVEL_TIERS) - 1:
        next_code = LEVEL_TIERS[current_idx + 1][1]
        if next_code in LEVEL_PRIVILEGES:
            current_priv_codes = {p["code"] for p in privilege_info["privileges"]}
            next_privs = LEVEL_PRIVILEGES[next_code]["privileges"]
            next_level_privileges = [
                p for p in next_privs 
                if p["code"] not in current_priv_codes
            ]
    
    return {
        "level_type": privilege_info["level_type"],
        "current_privileges": privilege_info["privileges"],
        "next_level_privileges": next_level_privileges,
    }
