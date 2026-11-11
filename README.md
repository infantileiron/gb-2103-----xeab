# 白鹭湾 · 河口样方生态分型

为六个采样断面寻找可解释、可复核的栖息类型：现场样方 → 标准化聚类 → 重采样稳定性 → 生态解释 → 站长归档 → CSV成果。

## 场景与工作流

模拟客户为白鹭湾生态监测站，18人、六个采样断面。站内原先把 `ecoplots_202611.csv` 拆成多张Excel，按盐度人工分组；量纲会支配距离、分组数缺少依据、跨批次分区不稳定。工作台替代人工分组和反复核验，承接实验室盐度/溶氧/浊度/叶绿素测定，下游供生态修复讨论组复核。种子数据为模拟观测，不是实际监测结论。

五个核心实体均有数据库表、model、schema、service、controller、route、前端API与store：SurveyDataset、ClusterStudy、ClusterRun、HabitatProfile、Report。首页与研究设计页共享 StudyTable；首页与分型解释共享 Scatter。

| 页面 | 主要动作 |
|---|---|
| 航测概览 | 读取真实运行结果、样方散点与研究列表 |
| 采样台账 | 导入CSV、验证完整数值与样本数量、查看原始量纲 |
| 分型配置 | 选择2–4个特征、候选k=2–6、设置5–60次重采样并入队 |
| 分型解释 | 对比轮廓分数、ARI分位、相关性、修改生态类型名称与复查意见 |
| 成果归档 | 创建成果、站长归档、下载每个样方的真实分型结果 |

## 一天的工作剧本

1. 10:00 陈研究员登录，核查 `ecoplots_202611.csv` 的360条样方，覆盖断面1–6。
2. 10:05 选择“十一月河口样方联合调查”，查看 BLW-0001 的盐度与溶解氧原始记录。
3. 10:10 新建“支汊溶氧分型复核”，选择四个特征，候选k为2–5，重采样20次，seed=2611。
4. 10:11 保存并运行；后台worker读取Redis队列，写入数据库及共享产物卷。
5. 10:12 查看候选轮廓分数与最佳k，检查ARI的5%–95%分位与真实样方散点。
6. 10:15 把“生态类型1”改为“低盐高氧栖息型”，补充淡水入流复查意见。
7. 10:20 生成成果记录，由林站长审核归档；归档后该运行的生态类型解释被锁定。
8. 10:25 生态观察员下载360条样方加一行表头的CSV，交研究讨论组结合季节条件复核。

## 快速启动

需要Docker Compose v2及镜像/软件包下载能力。在本目录执行：

```bash
cp .env.example .env
docker compose config --quiet
docker compose up -d --build
docker compose ps
docker compose exec -T backend python -m scripts.seed_demo
```

启动时 `SEED_DEMO=true` 自动填充一次演示数据，失败记录日志而不阻断服务。再次运行seed不会新增或覆盖现有自然键记录及用户修改。首次seed包含两项真实计算，启动健康检查有60秒宽限。

| 入口 | 地址 |
|---|---|
| 前端 | http://localhost:18202 |
| 后端OpenAPI | http://localhost:19202/docs |
| 健康检查 | http://localhost:19202/health |
| PostgreSQL | localhost:17702 |

| 角色 | 账号 | 密码 | 权限与典型动作 |
|---|---|---|---|
| admin | admin@estuary.local | Estuary2611! | 全部页面；站长审核归档、审计记录 |
| analyst | analyst@estuary.local | Estuary2611! | 导入观测、配置研究、运行分型、编辑解释、创建成果；不可归档 |
| viewer | viewer@estuary.local | Estuary2611! | 只读全部业务实体；只可下载已归档成果；写入返回403 |

上述账号仅作演示。部署前修改 `.env` 中JWT密钥与数据库密码。

## 算法口径与可复现条件

输入为10–5000条样方，四个数值字段 `salinity, oxygen, turbidity, chlorophyll`；研究选择其中至少两个。缺失值、NaN/无穷、常量特征、不同样方数量不足最大k均拒绝。输出来自Python计算，前端只绘制后端返回的点、分数、中心与相关矩阵。

**标准化与聚类选择**：每个特征按 `z=(x-mean)/std`（总体标准差）变换；KMeans每个k运行12个起点，选择最高轮廓分数。样本超过1500时固定seed抽样计算轮廓分数。轮廓系数 `(b-a)/max(a,b)` 中，a为簇内平均距离，b为最近其他簇的平均距离；分数并列时选较小k。类型按第一个所选特征的中心排序，CSV中心仍使用原始量纲。二维图明确展示前两个特征的标准分数，不是PCA投影。

**Bootstrap ARI稳定性**：每轮有放回抽取n条样方，重新拟合标准化器和同一k的KMeans，再预测全部原样本；与原分区计算Adjusted Rand Index。展示均值及5%/95%经验分位数；这不是生物学真实性置信区间，也不证明因果。每轮KMeans为8起点。

固定输入行顺序、特征顺序、seed=2611与依赖版本可复算。每次结果记录输入行JSON的SHA256、随机种子、候选分数、360个点及方法文字。默认模拟样本有三个分离群体，固定seed下应选k=3；实测轮廓分数约0.814678，ARI约1.0。真实野外数据未必有同等分离度。

## 技术栈与结构

| 层 | 交付配置 |
|---|---|
| 前端 | React18.3.1 / TypeScript5.7.3 / Vite6.4.6 / Nginx1.27 |
| 后端 | Python3.11 / FastAPI0.115.6 / NumPy2.2.6 / scikit-learn1.6.1 |
| 持久化 | PostgreSQL16 / psycopg3；数据库迁移SQL |
| 异步 | Redis7持久队列 / 独立Python worker / 心跳健康检查 |
| 横切 | 标准库HS256 JWT、PBKDF2密码摘要、请求审计、全局可恢复错误、任务排队配额5 |

`backend/src` 按 `config/constants/models/schemas/services/controllers/routes/middlewares/utils` 分责；`backend/migrations/001_initial.sql` 为五实体、用户及审计的幂等建表脚本；`backend/scripts/seed_demo.py` 为独立幂等种子入口。`frontend/src` 按 `api/stores/types/components/common/hooks/pages/router/utils/constants` 组织。

共享枚举位置：角色Role/运行状态RunStatus/成果状态ReportStatus定义于 `backend/src/constants/enums.py`，对应前端 `frontend/src/constants/enums.ts` 与角色类型 `frontend/src/types/index.ts`；后端权限在 `utils/security.py` 和controller，状态迁移在 `services/runs.py`、`services/reports.py`；前端状态展示在 `components/common/Status.tsx`，角色动作在各page与Layout。

## 环境变量与Docker说明

| 变量 | 作用 / 默认 |
|---|---|
| COMPOSE_PROJECT_NAME | estuary-lab；显式容器名与卷命名空间 |
| FRONTEND_PORT / BACKEND_PORT / DB_PORT | 18202 / 19202 / 17702 |
| POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD | Compose数据库连接信息 |
| JWT_SECRET | JWT HS256签名密钥 |
| SEED_DEMO | 是否在后端启动自动seed |
| DATABASE_URL | Compose注入PostgreSQL；本地可显式使用SQLite |
| REDIS_URL | Compose注入 redis://redis:6379/0 |
| TASK_MODE | Compose固定redis；本地单进程验证可显式设inline |
| ARTIFACT_DIR | 共享产物目录 /artifacts；worker保存每次结果JSON |

Compose恰好五个服务 `frontend/backend/worker/db/redis`，均设真实健康检查。backend等待db与redis；worker还等待backend完成初始化；frontend等待backend。三个命名卷分别保存数据库、Redis和计算产物。Redis与worker不映射宿主端口。Nginx `/api/` 去除代理前缀，后端路由为 `/datasets` 等，无双重api前缀。中文上层目录通过显式Compose项目名避免非法命名；实际中文路径容器启动仍待Docker验收。

后台任务采用Redis BLPOP单worker消费；若进程在取出任务后异常退出，尚不自动恢复该任务，需要研究员重跑。迁移目前为初始建表，不提供跨版本字段升级。默认无外部邮件或定时分发服务。

## 本地开发与验收

后端：在项目内创建venv，安装 `backend/requirements.txt`。常规开发仍建议使用Compose；无Docker时可显式使用SQLite和inline，以验证API与算法，不能据此认定PostgreSQL/Redis已验收。

```bash
cd backend
DATABASE_URL=sqlite:////tmp/estuary-local.sqlite3 TASK_MODE=inline SEED_DEMO=true ARTIFACT_DIR=/tmp/estuary-artifacts uvicorn src.main:app --host 127.0.0.1 --port 19202
```

前端：在 `frontend` 运行 `npm install`、`npm run dev`。Vite将 `/api` 转发至19202。生产构建为 `npm run build`。字体使用Google Fonts，离线时回退serif/sans-serif。

验收脚本、截图及报告位于批次 `test-artifacts/gb-2103/`，与源码分离。`tests/docker_acceptance.py` 使用标准库真实HTTP，要求健康接口明确返回redis模式，再验证三角色、排队计算、归档及导出；`tests/screenshots.mjs` 使用Playwright截取1440×900真实页面，需环境有可启动Chromium。测试后 `docker compose down -v --remove-orphans` 会删除演示卷。

本批环境限制及已执行结果见 `TESTING.md`：Compose静态验证通过，本地9项测试通过；实际5容器、React18依赖安装与页面截图未完成，因此整体状态为partial。

## License

MIT，见LICENSE。
