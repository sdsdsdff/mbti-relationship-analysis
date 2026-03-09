# MBTI Relationship Analysis

## 目录结构

```
mbti-relationship-analysis/
├── README.md                 # 项目说明
├── .gitignore               # Git 忽略规则
├── requirements.txt         # Python 依赖
├── pyproject.toml          # 项目配置
├── docs/                   # 文档
│   ├── design/            # 设计文档
│   │   ├── product-spec.md
│   │   ├── architecture.md
│   │   ├── schema.md
│   │   ├── mbti-baseline.md
│   │   └── signal-mapping.md
│   └── api/               # API 文档
├── src/                   # 源代码
│   ├── parsers/          # 输入解析层
│   │   ├── text_parser.py
│   │   ├── image_parser.py
│   │   └── schema.py
│   ├── analyzers/        # 分析层
│   │   ├── signal_extractor.py
│   │   ├── mbti_analyzer.py
│   │   └── relationship_analyzer.py
│   ├── models/           # 模型层
│   │   ├── llm_client.py
│   │   └── embeddings.py
│   └── utils/            # 工具函数
│       ├── config.py
│       └── logger.py
├── tests/                # 测试
│   ├── test_parsers/
│   ├── test_analyzers/
│   └── fixtures/
├── data/                 # 数据目录
│   ├── raw/             # 原始输入（不提交）
│   └── processed/       # 处理后数据（不提交）
└── scripts/             # 脚本
    ├── setup.sh
    └── run_analysis.py
```

## 开发环境设置

```bash
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 运行测试
pytest tests/
```

## 快速开始

```bash
# 分析聊天记录
python scripts/run_analysis.py --input data/raw/chat.md --output data/processed/report.json

# 使用自己的 API Key
export OPENAI_API_KEY="your-key-here"
python scripts/run_analysis.py --input data/raw/chat.md
```

### BYOK 配置示例

项目根目录提供了 `mbti.config.example.json`，推荐复制为 `mbti.config.json` 后再运行：

```bash
cp mbti.config.example.json mbti.config.json
export OPENAI_API_KEY="your-key-here"
python scripts/run_analysis.py --input data/raw/chat.md --config mbti.config.json
```

当前 BYOK provider 支持：`openai` / `openrouter` / `anthropic` / `custom`。

如果 BYOK 被禁用、没有 key，或请求 / 适配失败，pipeline 会自动回退到纯 heuristics 分析，并在输出 JSON 的 `report.metadata.llm_enrichment` 中记录状态。

## 当前状态

- ✅ 项目初始化
- ✅ 目录结构创建
- ✅ Phase 2 MVP 主干已可运行
- ✅ BYOK 分析流程骨架已接入
