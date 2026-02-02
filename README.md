# OKX量化交易系统（okxQuantitative）

> 最后更新：2026-02-02（执行者：Codex）

一个面向 OKX 的量化交易研究与可视化系统，包含 **FastAPI 后端**与 **Electron + Vue3 前端**，覆盖行情、策略、回测、（模拟/实盘）交易与实时监控等能力。

## 功能概览

- **行情**：REST + WebSocket，支持 ticker / K 线数据获取与缓存
- **策略**：内置多种策略（双均线、网格、MACD、RSI、KDJ、布林带、混合策略等），支持加载外部策略目录
- **回测**：策略选择、参数配置、回测结果与收益曲线展示
- **交易**：支持模拟盘/实盘两套密钥与模式切换（由 `config/.env` 控制）
- **接口文档**：启动后访问 `http://127.0.0.1:8000/docs`
- **健康检查**：`/health`；综合状态：`/status`

## 项目结构

- `backend/`：FastAPI 后端（入口：`backend/app/main.py`）
- `frontend/`：Electron + Vue3 前端（入口：`frontend/src/`）
- `config/`：配置（示例：`config/.env.example`）
- `data/`：本地 SQLite 数据库与行情数据产物（默认：`data/market.db`）
- `logs/`：运行日志
- 根目录 `*.bat`：Windows 一键安装/启动/重置

## 快速开始（Windows）

### 1) 安装依赖

前置要求：
- Python **>= 3.10**
- Node.js（建议 **18+**）
- `uv`（脚本会尝试自动安装；失败可自行安装后重试）

一键安装：

```bat
install.bat
```

### 2) 配置 OKX 与运行参数

将 `config/.env.example` 复制为 `config/.env`，并按需修改：

- 模拟盘密钥：`OKX_DEMO_API_KEY` / `OKX_DEMO_SECRET_KEY` / `OKX_DEMO_PASSPHRASE`
- 实盘密钥：`OKX_LIVE_API_KEY` / `OKX_LIVE_SECRET_KEY` / `OKX_LIVE_PASSPHRASE`
- 模式选择：`OKX_USE_SIMULATED=true|false`
- API：`API_HOST` / `API_PORT` / `API_DEBUG`
- 数据库：`DATABASE_PATH`（可选，不填默认 `data/market.db`）
- 外部策略：`EXTERNAL_STRATEGIES_DIR`（可选，外部策略目录）
- 缓存与限频：`CACHE_*` / `OKX_RATE_LIMIT`

### 3) 启动系统

```bat
start.bat
```

启动后默认访问：
- 后端：`http://127.0.0.1:8000`
- API 文档：`http://127.0.0.1:8000/docs`
- Vite（开发端口）：`http://127.0.0.1:5173`

### 4) 重置数据（可选）

```bat
reset.bat
```

如需同时删除 `config/.env`（清除密钥/配置），使用：

```bat
reset.bat /config
```

## 手动启动（开发）

### 后端（FastAPI）

```powershell
cd backend
uv sync
uv run python run.py
```

或直接运行 Uvicorn：

```powershell
cd backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 前端（Electron + Vue3）

```powershell
cd frontend
npm install
npm run dev
```

## 测试

后端单元测试（收集 `backend/tests/test_*.py`）：

```powershell
cd backend
uv run pytest
```

手动脚本（会读写本地数据库，且可能触发网络请求）：

```powershell
uv run python backend/test_data.py
```

## 构建打包

Electron 打包（electron-builder）：

```powershell
cd frontend
npm run build
```

## GitHub 上传建议

- `.gitignore` 已忽略 `config/.env`、数据库文件（`*.db`）与 `node_modules/`，提交前确认是否符合你的预期。
- 当前 `.gitignore` 也忽略了 `docs/`：如果你希望将 `docs/` 一并提交到 GitHub，请移除 `.gitignore` 中的 `/docs` 规则。

## 免责声明

本项目仅用于学习与研究，不构成任何投资建议。使用实盘功能前请充分评估风险，盈亏自负。

