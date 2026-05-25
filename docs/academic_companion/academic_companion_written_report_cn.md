# Academic Companion 书面报告（中文）

## 1. 项目概述

本次工作围绕 `ROKID_Agent_Tutor` 后端仓库完成了 `academic_companion` 模块的统一集成。该模块面向 Rokid 眼镜及现有 WebSocket 网关，对外保持单一入口，不额外新增独立网关模块。

统一对外接口如下：

- `agent_type = academic_companion`
- `async def handle_request(event_type, session_id, payload)`

在该统一入口下，目前已整合三项内部能力：

- 学术演讲辅助（presentation）
- 学习反思教练（reflection_coach）
- 学习状态感知（learning_state_guardian）

## 2. 工作目标

本阶段的主要目标包括：

1. 将个人功能模块接入团队共享后端仓库。
2. 保持与现有 WebSocket 网关协议兼容。
3. 不破坏其他组员已有模块，包括 `essay_grading`、`note_assistant` 和现有 `ielts_speaking` 主逻辑。
4. 为后续联调、演示和集成测试提供统一请求格式、调用样例和基础测试脚本。

## 3. 系统接入方式

本项目接入采用“单一外部接口 + 内部多能力分发”的结构。

### 3.1 网关层

在网关文件中新增了 `academic_companion` 路由，使后端能够识别并转发该模块的请求。外部系统只需要向 WebSocket 网关发送标准 JSON 信封，并将 `agent_type` 指定为 `academic_companion`。

### 3.2 模块层

`academic_companion` 内部再根据 `event_type` 和 `payload` 中的能力信息进行二次分发，从而统一承载三类功能，而不需要在网关中额外增加多个新的 agent。

### 3.3 兼容性

本模块保持与现有网关返回格式兼容，统一返回：

- 成功：`{"status":"success","data":{...}}`
- 失败：`{"status":"error","message":"..."}`

## 4. 已完成内容

### 4.1 学术演讲辅助

已完成的主要能力包括：

- 演讲任务 intake 与 mission 更新
- script section / 演讲卡片组织
- teleprompter chunk 控制
- rehearsal 记录与分析
- readiness、drill、Q&A preparation
- lightweight `live_hud` 输出

### 4.2 学习反思教练

已完成的主要能力包括：

- reflection focus 设置
- reflection capture
- coach summary
- signature
- reflection questions
- next-session experiments
- evidence cards
- coach memo
- provider status 外壳信息

### 4.3 学习状态感知

已完成的主要能力包括：

- task-mode-aware 状态判断
- core metrics：
  - `focus_score`
  - `cognitive_load`
  - `behavioral_alignment`
  - `fatigue_risk`
  - `uncertainty_score`
  - `state_hint`
- sustained difficulty tracking
- sensor-style / posture-style 输入映射
- state explanation 输出

## 5. 测试与验证

本次已完成以下验证工作：

1. 模块语法检查通过。
2. guardian smoke test 通过。
3. reflection smoke test 通过。
4. presentation smoke test 通过。
5. 真实本地 WebSocket 网关往返验证通过。

在真实网关验证中，已确认以下三类能力都可以通过 `academic_companion` 正常返回 `success`：

- `presentation`
- `reflection_coach`
- `learning_state_guardian`

## 6. 兼容性修复

在真实 WebSocket 联调过程中，发现 Windows 控制台在 `gbk` 编码环境下打印 emoji 日志会触发 `UnicodeEncodeError`，导致连接异常中断。

因此补充了最小兼容性修复：

- 在网关中加入安全日志输出函数
- 保持原有路由和协议不变
- 仅修复控制台日志输出兼容问题

该修复完成后，真实本地 WebSocket 往返验证成功。

## 7. 边界说明

本次工作未修改其他组员模块的业务实现，包括：

- `essay_grading`
- `note_assistant`
- 现有 `ielts_speaking` 主逻辑

改动范围主要集中在：

- `academic_companion` 模块本身
- 必要的网关接入
- 测试与样例文档
- 网关日志兼容性修复

## 8. 当前成果总结

截至当前阶段，`academic_companion` 已成功接入 `ROKID_Agent_Tutor` 的 `Dev` 分支，并完成以下目标：

- 三项内部能力统一集成
- 与现有 WebSocket 网关兼容
- 提供调用样例与 smoke test
- 完成真实本地网关联调

这意味着本模块已经具备后续团队联调、系统演示和继续集成的基础条件。

## 9. 后续建议

后续可继续推进以下方向：

1. 在 `Dev` 分支上进行多人联调。
2. 根据前端或设备侧反馈微调 payload 结构。
3. 进一步补强本地原项目中尚未完整迁入的高级能力。
4. 在完成团队联调后，再考虑从 `Dev` 进入 `main`。
