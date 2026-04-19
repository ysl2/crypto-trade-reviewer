# 成交复盘

一个本地运行、只读的多交易所历史成交可视化工具。

它的目标很简单：把你在不同交易所的真实成交拉回来，混合到一张图里看清楚自己以前到底买了什么、卖了什么。

这个项目：

- 只做分析，不下单
- 只看真实成交，不看未成交订单
- 支持把多个交易所的同一市场混在一起看
- 主图只保留两部分：
  - 上面：净成交点
  - 下面：基础币累计数量折线

## 现在支持什么

- Binance Spot
- OKX Spot
- Bitget Spot
- Gate Spot
- 中文 / English 界面切换
- 浏览器时区显示
- Docker Compose 部署

## 最快启动

```bash
cd ~/Documents/crypto-trade-reviewer
cp .env.example .env
docker compose up --build -d
```

打开：

```text
http://localhost:8513
```

检查服务是否正常：

```bash
curl -sf http://localhost:8513/_stcore/health
```

## 怎么用

1. 打开页面。
2. 展开“交易所 API 导入”。
3. 选择交易所。
4. 填入只读 API Key / Secret。
5. 输入想导入的市场，比如 `BTCUSDT ETHUSDT SOLUSDT`。
6. 选择时间范围。
7. 点击导入。
8. 导入完成后，在主界面切换市场和时间粒度看图。

## 这张图怎么看

上面的点：

- 每个点代表一个时间桶内的净成交结果
- 价格是这个时间桶内所有成交的合并均价
- 买卖不会分成两个点，而是合并成一个净结果点
- 点越大，说明这个时间桶内的净成交量越大
- 水位线是当前参考价，会跟随当前市场切换

下面的线：

- 表示基础币累计数量变化
- 买入会往上
- 卖出会往下

## 数据保存在哪里

项目数据默认保存在：

```text
.data/trades.sqlite3
```

这里面会保存：

- 导入的历史成交
- 页面里填写过的交易所 API 表单内容

注意：

- 这些内容只保存在你本地
- 当前版本的 API 凭证是本地明文保存
- 适合个人本机使用，不适合多人共用机器

## 安全建议

- 只使用只读 API
- 不要开启交易、提现、转账权限
- 不要把 `.env`、`.data/`、数据库文件提交到 Git
- 不要把包含 API Key 的截图发出去

仓库已经忽略这些敏感文件：

- `.env`
- `.data/`
- `*.sqlite3`
- `secrets.toml`

## 常用命令

查看日志：

```bash
docker compose logs -f
```

重启：

```bash
docker compose restart
```

停止：

```bash
docker compose down
```

## 常见问题

### 页面打不开

先看：

```bash
docker compose ps
curl -sf http://localhost:8513/_stcore/health
```

### 导入后没数据

这个工具不会自动抓取，必须先手动导入真实成交。

### 某些很早的成交拉不到

有些交易所官方接口本来就限制历史范围，这不是本项目额外加的限制。

## 本地开发运行

```bash
cd ~/Documents/crypto-trade-reviewer
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.address 0.0.0.0 --server.port 8513
```

测试：

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/pytest -q
.venv/bin/python -m compileall app.py src tests
```
