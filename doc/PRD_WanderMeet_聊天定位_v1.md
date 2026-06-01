# 旅聚 WanderMeet · 聊天发送定位 PRD v1.0

| 项 | 内容 |
|----|------|
| 版本 | v1.0 |
| 日期 | 2026-05-21 |
| 范围 | 活动群聊、城市大群、私聊 |

---

## 1. 目标

用户在约见面、拼集合点时，可在群内/私聊**发送地图位置**，对方点击后在系统地图中打开导航。

## 2. 场景

| 场景 | 说明 |
|------|------|
| 活动群 | 报名成员在活动群聊发汇合点 |
| 城市大群 | 同城用户在长期大群发见面地点 |
| 私聊 | 活动群内发起私聊后约定地点 |

## 3. 功能说明

### 3.1 发送

1. 聊天输入栏点击 **定位图标**（地图 pin）。
2. 进入 **选点页**（与发活动相同 POI 能力，`from=chat`）。
3. 选择地点后返回聊天页，**自动发送**一条定位消息。
4. 消息类型 `msgType=location`，字段：`locationName`、`address`（可选）、`lat`、`lng`。

### 3.2 展示

- 气泡：地点名称 + 地址（若有）+「点击打开地图」。
- 自己发送：右侧气泡样式与文本一致。
- 长按：可复制「名称 + 地址 + 坐标」。

### 3.3 打开地图

- 点击定位气泡 → 调用 `uni.openLocation`（微信/抖音需已配置定位相关隐私说明）。

### 3.4 消息列表

- 「消息」Tab 最近一条：`[位置] 地点名`（过长截断）。

## 4. 非功能

- **不**自动发送用户实时 GPS；必须用户选点确认。
- 经纬度校验：合法范围，禁止 (0,0)。
- 与文本消息相同的内容安全策略（定位名称长度上限）。

## 5. 接口（后端）

- 发消息：`POST /activities/{id}/messages`、`POST /direct-chats/{threadId}/messages`
- Body 示例：

```json
{
  "msgType": "location",
  "locationName": "三里屯太古里",
  "address": "北京市朝阳区…",
  "lat": 39.933,
  "lng": 116.454
}
```

- 拉消息：响应含 `locationName`、`address`、`lat`、`lng`。
- 存储：`msg_type=location`，`text_content` 为 JSON（无需 DB 迁移）。

## 6. 实现文件索引

| 端 | 路径 |
|----|------|
| 后端 | `app/services/chat_location.py`、`app/services/chat_message_payload.py` |
| 后端 | `app/schemas/activity.py`、`app/schemas/direct_chat.py` |
| 前端 | `src/pages/chat-detail/chat-detail.vue` |
| 前端 | `src/pages/direct-chat-detail/direct-chat-detail.vue` |
| 前端 | `src/pages/location-picker/location-picker.vue` |
| 前端 | `src/components/ChatLocationBubble/`、`src/utils/chatLocation.js` |

## 7. 验收

- [ ] 活动群可发、可收、可点开地图
- [ ] 城市大群同上
- [ ] 私聊同上
- [ ] 消息列表摘要正确
- [ ] Mock 模式可用
