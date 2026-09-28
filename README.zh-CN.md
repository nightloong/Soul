# PersonaForge

[English](./README.md) | [简体中文](./README.zh-CN.md)

PersonaForge 是一款本地优先、以证据为依据的人格研究工具。它可以导入对话、追溯每条推断结论的来源、记录纠错、检索相关证据，并生成明确标注为“模拟”的人物回复。本仓库已实现随附执行方案的第 0–12 阶段。

## 本地运行

需要 Python 3.11+、Node.js 22+，以及支持 FTS5 的 SQLite。下方命令使用 Unix 系统的虚拟环境路径；Windows 用户请将 `.venv/bin/python` 替换为 `.venv\Scripts\python.exe`。

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
npm ci
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m uvicorn personaforge.main:app --host 127.0.0.1 --port 8000
```

在第二个终端运行：

```bash
npm run build
npm run preview
```

打开 Vite 输出的网址，通常是 `http://127.0.0.1:4173`。构建后的前端会将 `/api` 请求代理到本地后端。在包含中文字符的 Windows 路径下，Vite 开发模式的依赖优化器可能失败；`build` 加 `preview` 是已验证的运行方式。

## 首次导入

网页界面支持数据集、人物、导入预览与确认、搜索、证据与主张查看、纠错、证据蒸馏、人物模拟和会议分析。`examples/` 中是可供试用的虚构数据。支持 JSON、JSONL、CSV、TXT 和 Markdown。导入预览会列出未确定的人物映射和 SHA-256 哈希；正式导入需要提交该哈希并明确映射。重复导入同一份源文件不会产生重复事件。

也可以使用 CLI：

```bash
.venv/bin/python -m personaforge.cli dataset create "Demo"
.venv/bin/python -m personaforge.cli person create "Ava" --dataset DATASET_ID
.venv/bin/python -m personaforge.cli import preview examples/synthetic-chat/project.jsonl
```

正式导入时使用预览返回的哈希和原始发言人名称。具体参数见 `.venv/bin/python -m personaforge.cli import apply --help`。

## 连接模型

若要使用兼容 OpenAI API 的模型服务，请在后端进程的环境变量中设置 `PERSONAFORGE_MODEL_BASE_URL`、`PERSONAFORGE_MODEL_NAME` 和 `PERSONAFORGE_MODEL_API_KEY`。`.env.example` 列出了这些变量及本地端点示例。PowerShell 中可以先执行 `$env:PERSONAFORGE_MODEL_NAME='model-name'`，再以相同方式设置其他变量，然后启动 Uvicorn。

导入、统计、搜索、纠错和人格重建不依赖模型。证据蒸馏和人物模拟会调用配置的模型。API 密钥仅从环境变量读取，不写入 SQLite。

证据蒸馏作为后台任务运行。人物页面会轮询已保存的进度，失败后可重试；也可通过 `GET /api/distillation/jobs/{id}` 查询状态。失败状态只返回异常类型，不暴露模型错误正文。

## 验证

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m alembic check
npm run lint
npm test
npm run build
```

Windows 上的浏览器测试使用 Microsoft Edge。分别在两个终端启动 8000 端口的 API 和 `npm run preview -- --port 5173`，然后设置 `PERSONAFORGE_E2E_EXTERNAL=1` 并执行 `npx playwright test`。在 PowerShell 中，可用 `$env:PERSONAFORGE_E2E_EXTERNAL='1'` 设置该变量。环境允许时，也可使用 Playwright 自带的 Web 服务器配置。

## 隐私与来源追溯

私有源文件应放在 `data/private/`；Git 会忽略该目录、`.env` 和 SQLite 数据库。蒸馏或模拟时，外部模型端点会收到选中的事件片段；使用本地模型端点可让这部分处理留在设备上。主张、记忆、模拟记录和会议结论均保留证据引用。模拟回复始终明确标注为生成内容，不会被表述为当事人的真实发言。

架构、数据模型、隐私、提示词边界和阶段报告见 `docs/`。可用 `.venv/bin/python scripts/benchmark_100k.py` 运行 10 万条虚构事件的基准测试；Windows 用户请替换虚拟环境路径。

## 依赖与许可证

Python 运行依赖：FastAPI（MIT）、Uvicorn（BSD-3-Clause）、Pydantic（MIT）、SQLAlchemy（MIT）、Alembic（MIT）、python-multipart（Apache-2.0）、ijson（BSD-3-Clause）和 httpx（BSD-3-Clause）。前端依赖：React、React DOM、React Router、Vite、ESLint、Vitest、Testing Library 和 jsdom（MIT）；TypeScript 和 Playwright（Apache-2.0）。`package-lock.json` 记录 JavaScript 依赖的确切版本；各依赖自身的许可证文件为准。
