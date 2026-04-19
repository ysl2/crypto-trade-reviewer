# 成交复盘

`成交复盘` 是一个本地运行、只读的多交易所历史成交可视化工具，用来把你在不同交易所上的现货实际成交统一拉回本地，按同一个市场混合复盘。

当前版本只保留一张核心主图：

- 上半部分：按时间粒度聚合后的净流向散点
- 下半部分：基础币累计数量折线
- 同一个 `BASE/QUOTE` 市场会把多交易所数据混在一起展示
- 主图里的价格点使用该时间桶内所有成交的合并均价
- 当前价格线优先使用 Binance 现货参考价，并自动刷新

它不做下单，不做自动策略，不做订单生命周期管理，只负责复盘历史实际成交。

## 当前能力

- 本地运行，数据默认存到本地 SQLite
- 支持 4 家现货只读 API 导入真实成交：
  - Binance
  - OKX
  - Bitget
  - Gate.io
- 市场按 `基础币/计价币` 归一，例如 `BTC/USDT`
- 同一市场下，多交易所数据会混在一张主图里
- 时间粒度支持 `1h / 4h / 1d / 1w / 1M / 1y`
- 只导入“实际成交 fills”，不导入挂单、撤单或未成交订单

## 推荐运行方式：Docker Compose

```bash
cd ~/Documents/crypto-trade-reviewer
cp .env.example .env
docker compose up --build -d
```

启动后访问 `http://localhost:8513`

健康检查：

```bash
curl -sf http://localhost:8513/_stcore/health
```

常用命令：

```bash
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d
```

数据会持久化到项目目录下的 `.data/trades.sqlite3`。

## 导入与使用

1. 打开页面后，先展开“交易所 API 导入”。
2. 选择交易所页签，填写只读 API Key / Secret。
3. 输入需要导入的市场，例如 `BTCUSDT ETHUSDT SOLUSDT`。
4. 选择时间范围并开始导入。
5. 导入完成后，在主界面选择市场和时间粒度查看混合后的成交主图。

主图说明：

- 主图上方散点：按时间桶合并后的净流向点
- 主图下方折线：基础币累计数量变化
- 点位价格：该时间桶内所有成交的 `总成交额 / 总成交量`
- 点大小：按该时间桶的净基础币数量缩放

## API 与安全

推荐先准备 `.env`：

```bash
cp .env.example .env
```

然后按需填写以下环境变量：

- `BINANCE_API_KEY`
- `BINANCE_API_SECRET`
- `BINANCE_BASE_URL`
- `OKX_API_KEY`
- `OKX_API_SECRET`
- `OKX_API_PASSPHRASE`
- `OKX_BASE_URL`
- `BITGET_API_KEY`
- `BITGET_API_SECRET`
- `BITGET_API_PASSPHRASE`
- `BITGET_BASE_URL`
- `GATE_API_KEY`
- `GATE_API_SECRET`
- `GATE_BASE_URL`

安全建议：

- 只为这个工具创建单独的只读 API Key
- 明确关闭交易、提现、转账等权限
- 不要把 `.env`、`.data/`、数据库文件或含凭证的截图提交进 Git
- 仓库里只保留 `.env.example` 占位模板

## 交易所范围与限制

接入范围：

- Binance Spot
- OKX Spot
- Bitget Spot
- Gate Spot

不同交易所的历史限制不一致：

- Binance：按官方账户成交接口分页，已兼容长时间区间导入
- OKX：官方接口只支持近 90 天成交
- Bitget：官方接口只支持近 90 天成交
- Gate：按时间窗口分页拉取

如果请求时间超出交易所官方可返回范围，页面会提示并在支持的交易所上自动截断。

## 本地 Python 运行（备用）

```bash
cd ~/Documents/crypto-trade-reviewer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8513
```

## 测试与校验

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
.venv/bin/python -m compileall app.py src tests
```

## 常见问题

### 8513 端口没响应

- 先执行 `docker compose ps`
- 再看 `docker compose logs -f`
- 用 `curl -sf http://localhost:8513/_stcore/health` 检查容器内应用是否健康

### Binance 导入报时间范围错误

- 当前版本已经兼容长时间区间分页
- 如果仍报错，优先检查 API 权限、系统时间、Base URL 是否被改错

### OKX / Bitget 拉不到很早的历史成交

- 这是交易所官方接口限制，不是本项目额外加的限制
- 页面会提示并自动截断到交易所允许的历史窗口

### 页面能打开，但没有数据

- 这个工具不会自动抓取，必须先在页面里手动导入实际成交
- 导入后数据会落到本地 `.data/trades.sqlite3`

## 设计取舍

- 只做现货实际成交，不做合约、杠杆、理财
- 只做只读复盘，不做交易执行
- 主图按时间桶聚合，不展示市场 K 线背景
- 价格水位线只作为参考，不参与任何持仓或成本计算
