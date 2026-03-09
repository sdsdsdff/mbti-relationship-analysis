# MBTI Relationship Analysis

> 一个基于私域聊天记录的 AI + 心理学人格与关系分析助手

## 📌 项目简介

通过对聊天记录进行结构化分析，帮助用户理解**自己、对方与双方关系**，并输出**可解释、可回溯、有证据锚点**的沟通与互动建议。

### 核心特性

- 🧠 **科学心理学框架**：基于 MBTI、Big Five、依恋理论等心理学构念
- 🔍 **证据驱动分析**：所有判断都绑定聊天片段证据
- 🔐 **隐私优先**：BYOK（自带模型 Key）、可自部署
- 📊 **结构化输出**：可能类型 + 当前阶段 + 优势短板 + 进阶建议
- 🎯 **关系洞察**：不只分析个人，更关注双方互动模式

## 🎯 产品定位

这不是：
- ❌ AI 算命器
- ❌ 宿命论 MBTI 配对器
- ❌ 操控/拿捏对方的工具

这是：
- ✅ 自我理解工具
- ✅ 关系分析助手
- ✅ 沟通副驾
- ✅ 私域关系决策支持工具

## 🧭 方法论原则

1. **前台可以主打 MBTI，后台不能只靠 MBTI**
2. **V1 先做"看懂现在"，不做"预测未来"**
3. **重要判断必须给出证据与不确定性**
4. **显式区分：稳定倾向 / 关系中的模式 / 当前状态**
5. **不把 MBTI 玄学化、宿命化**

## 🏗️ 架构设计

### 五层架构

```
多模态输入解析层 → 规则壳 → Embedding 预处理层 → 子模型层 → 主模型层
```

1. **多模态输入解析层**：文本/截图 → 结构化对话
2. **规则壳**：流程编排、缓存、审计
3. **Embedding 预处理层**：语义向量化、片段召回
4. **子模型层**：局部片段理解、信号提取
5. **主模型层**：全局综合判断、报告生成

## 📥 输入支持

- ✅ Markdown 聊天记录
- ✅ TXT 文本导出
- ✅ 聊天截图 / 长截图
- 🔜 微信/QQ 导出格式
- 🔜 Telegram/WhatsApp 导出

## 📤 输出结构

### 核心报告卡片

1. **可能类型**：你大概率是什么类型（附备选）
2. **当前阶段**：初阶/成长中/整合中/失衡中
3. **优势/短板**：天然强项 vs 容易吃亏的地方
4. **进阶建议**：该补哪块、怎么练、避免什么
5. **关系卡点**（双人分析）：你们卡在哪里、主要误解点

### 证据层

- 聊天片段锚点
- 行为模式时间线
- 置信度与反证
- 区分聊天证据 vs 用户补充信息

## 🗺️ 路线图

### Phase 0：立项与方法论收敛 ✅
- [x] 产品定位
- [x] 方法论设计
- [x] 架构设计
- [x] 隐私路线

### Phase 1：文档与 Schema（当前）
- [ ] 内部消息 schema
- [ ] 行为信号 schema
- [ ] 报告 IR / 卡片结构
- [ ] 背景补充信息 schema

### Phase 2：开源 MVP
- [x] md/txt 导入
- [x] 基础归一化
- [x] 基础信号抽取
- [x] 基础报告生成
- [x] BYOK 分析流程

## 🤖 BYOK MVP 使用

### 1. 准备配置

可参考根目录的 `mbti.config.example.json`：

```json
{
  "byok": {
    "enabled": true,
    "provider": "openai",
    "model": "gpt-4.1-mini",
    "api_key_env": "OPENAI_API_KEY",
    "temperature": 0.2,
    "max_tokens": 900
  }
}
```

- `provider` 当前支持：`openai` / `openrouter` / `anthropic` / `custom`
- `custom` 模式需要额外提供 `base_url`
- 不要把真实密钥写进仓库，优先通过环境变量注入

### 2. 运行分析入口

```bash
cp mbti.config.example.json mbti.config.json
export OPENAI_API_KEY="your-key-here"
python scripts/run_analysis.py \
  --input data/raw/chat.md \
  --config mbti.config.json \
  --output data/processed/analysis.json
```

- 不传 `--output` 时，会直接把 JSON 打印到标准输出
- 加 `--report-only` 时，只输出最终报告 JSON

### 3. Fallback 行为

当前 BYOK enrichment 是**可选增强层**，不会阻断原有 heuristics pipeline：

- `byok.enabled = false`：直接走纯 heuristics 报告
- 已启用但缺少 key：直接 fallback 到纯 heuristics 报告
- LLM 请求或结果适配出错：直接 fallback 到纯 heuristics 报告

上述状态会记录到 `report.metadata.llm_enrichment`，便于区分：

- 是否启用了 LLM enrichment
- 是否实际尝试调用
- 是否成功使用
- fallback 原因（如 `disabled` / `missing_api_key` / `client_error`）

### 4. 当前边界

- 当前实现重点是 **prompt 打包 / provider 请求构建 / 结果适配 / pipeline 接入**
- 已提供可 mock 的 client 接口与测试骨架
- **未做真实联网成功验证**，所以更适合作为本地 MVP 骨架与后续联调起点

### Phase 3：增强解释与隐私
- [ ] 证据回查优化
- [ ] 候选类型与 facet 卡片
- [ ] 本地脱敏模块
- [ ] 置信度与反证机制

### Phase 4：长期对象级建模
- [ ] 多次分析结果串联
- [ ] 关系时间线
- [ ] 对象级历史画像
- [ ] 复盘与趋势变化

## 🔐 隐私承诺

- 开源
- Self-host / Local-first 友好
- BYOK（自带模型 Key）
- 不强求云账号体系
- 尽量减少黑箱感
- 后续逐步补本地脱敏

## 📚 相关文档

详细设计文档见 `docs/` 目录：
- `design/product-spec.md` - 产品规格
- `design/architecture.md` - 架构设计
- `design/schema.md` - 数据结构
- `design/mbti-baseline.md` - MBTI 权威基线
- `design/signal-mapping.md` - 信号映射手册

## 🤝 贡献

欢迎贡献！请先阅读 `CONTRIBUTING.md`。

## 📄 License

MIT License

---

**状态**：🟡 Phase 2 - MVP 主干已就绪，BYOK 骨架已接入
**发起日期**：2026-03-07
**最后更新**：2026-03-09
