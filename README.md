# LangGraph 智能旅行助手

本项目由 `code/chapter13/helloagents-trip-planner` 重构而来，输出目录为 `E:\Python Project\hello-agents\travel_agent`。

核心变化：

- 后端智能体编排从教学型 Agent 改为 LangChain / LangGraph 工作流。
- 后端统一使用 `loguru`，日志写入 `logs/app.log`，按大小轮转。
- 高德、Unsplash、LLM 调用都在服务层封装，失败时自动降级。
- 景点和酒店返回统一 `image` / `image_url` 字段，前端不暴露图片服务密钥。
- 前端支持历史记录、JSON 导入、JSON 导出，并保留图片和 PDF 导出。
- 地图组件独立为 `TripMap.vue`，支持景点和酒店 Marker、信息窗和自动缩放。

## 目录结构

```text
travel_agent/
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph 工作流与状态
│   │   ├── api/             # FastAPI 路由
│   │   ├── core/            # 日志等基础设施
│   │   ├── models/          # Pydantic 模型
│   │   └── services/        # 高德、图片、LLM 服务
│   └── requirements.txt
├── frontend/
│   ├── src/components/      # TripMap 地图组件
│   ├── src/utils/           # localStorage 历史记录
│   ├── src/views/           # 首页、结果页
│   └── package.json
└── logs/
```

## 环境变量

后端在 `backend/.env` 或项目根目录 `.env` 中读取：

```env
AMAP_API_KEY=你的高德Web服务Key
UNSPLASH_ACCESS_KEY=你的Unsplash Access Key
LLM_API_KEY=你的LLM Key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL_ID=gpt-4o-mini
LOG_LEVEL=INFO
APP_DEBUG=false
APP_HOST=0.0.0.0
APP_PORT=8000
```

前端在 `frontend/.env` 中读取：

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_AMAP_WEB_JS_KEY=你的高德Web端JS API Key
VITE_AMAP_SECURITY_JS_CODE=你的高德安全密钥
```

缺少外部 Key 时后端仍可启动：POI、天气、图片和 LLM 会走降级数据，保证接口不崩溃。

## 启动后端

```bash
cd "E:/Python Project/hello-agents/travel_agent/backend"
python run.py -m pip install -r requirements.txt
python run.py
```

API 文档：`http://localhost:8000/docs`

## 启动前端

```bash
cd "E:/Python Project/hello-agents/travel_agent/frontend"
npm install
npm run dev
```

前端地址：`http://localhost:5173`

## LangGraph 工作流

工作流节点顺序：

1. 输入解析与参数标准化
2. 景点搜索
3. 天气查询
4. 酒店推荐
5. 图片补全
6. 行程规划
7. 地图数据构建
8. 结果校验与格式化

每个节点都通过 Pydantic 模型校验输入输出，并把异常写入状态中的 `errors`，外部服务失败时使用本地降级数据继续生成方案。

## 历史记录方案

当前采用前端 `localStorage` 保存最近 20 条记录，字段包含：

- 用户输入参数
- 生成时间
- 目的地
- 出行天数
- 完整旅行方案

该方案无需额外数据库，适合当前章节项目复杂度。后续如需多设备同步，可再增加 FastAPI + SQLite 的服务端历史记录。

## 导入导出

结果页支持：

- 导出 JSON：包含完整结构化 `TripPlan`，可再次导入恢复。
- 导入 JSON：支持导入纯 `TripPlan`、`{ data: TripPlan }` 或本系统导出的 JSON。
- 导出图片 / PDF：保留原有导出能力；导出时会隐藏动态高德地图，避免第三方 Canvas 跨域导致失败。

## 日志

日志配置在 `backend/app/core/logging.py`：

- 控制台输出
- 文件输出：`logs/app.log`
- 默认轮转：`10 MB`
- 默认保留：`14 days`

日志只记录 Key 是否配置，不输出 API Key、Token 等敏感值。
