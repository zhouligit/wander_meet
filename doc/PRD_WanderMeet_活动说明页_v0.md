# WanderMeet 活动说明页（V0）

更新时间：2026-06-13  
关联：活动详情 `description` 改展示为 **活动简介**；完整说明独立新页。

---

## 1. 产品决策

| 决策点 | 结论 |
|--------|------|
| 活动简介 | 仍用现有 `description`，详情页标题改为「活动简介」 |
| 完整说明 | **新页面**「活动说明页」，详情页底部入口「查看完整活动说明」 |
| 内容形态 | **全站一套模板** + 各章节自由编辑 |
| 概况/费用 | **引用同步**活动主字段（名称、时间、地点、人数、费用），说明页不重复维护 |
| 未填写 | 说明页展示「组织者暂未补充」；组织者可「去编辑」 |
| 命名 | 详情：活动简介；新页标题：`活动说明｜{活动标题}` |

---

## 2. 模板章节（全站）

| 序号 | key | 标题 | 存储 |
|------|-----|------|------|
| 一 | （引用） | 活动概况 | 自动从活动字段生成 + 可选 `overviewNote` |
| 二 | `itinerary` | 行程安排 | 持久化 |
| 三 | `equipment` | 装备要求 | 持久化 |
| 四 | `enrollmentRequirements` | 报名条件 | 持久化 |
| 五 | `feeNote` | 费用说明 | 引用 `feeType/feeAmount` + `feeNote` 补充 |
| 六 | `registration` | 报名方式 | 持久化 |
| 七 | `risk` | 风险提示 | 持久化 |
| 八 | `environment` | 环保要求 | 持久化 |

`guideFilled`：任一持久化章节非空即为 `true`。

---

## 3. 后端（`wander_meet`）

迁移：`20260613_0030_activity_guide.py` → `activities.guide_sections` JSON。

| 能力 | API | 状态 |
|------|-----|------|
| 模板元数据 | `GET /meta/activity-guide` | ✅ |
| 详情含说明 | `GET /activities/{id}` → `guideSections`、`guideFilled`、`guideOverview` | ✅ |
| 发布/编辑 | `POST/PATCH /activities` body `guideSections` | ✅ |
| 内容安全 | 保存时 `msgSecCheck`（scene=论坛） | ✅ |

---

## 4. 小程序（`lv_ju/travel-together`）

| 页面/模块 | 说明 |
|-----------|------|
| `activity-detail` | 「活动简介」+ 跳转按钮 |
| `activity-guide` | 只读说明页 |
| `activity-guide-edit` | 组织者编辑（从详情/编辑活动进入） |

---

## 5. 自测

1. 新活动未填说明 → 详情可点入口 → 说明页「组织者暂未补充」
2. 组织者编辑并保存 → 说明页展示各章节；概况时间与详情一致
3. 修改活动费用/地点 → 说明页概况/费用引用自动更新
