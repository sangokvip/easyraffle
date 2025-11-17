# 抽奖 Telegram Bot

使用 `python-telegram-bot` + MySQL 构建的群组抽奖机器人。群管理员可配置抽奖、指定中奖人数/策略以及设置预设中奖者，普通用户用 `/join` 报名，管理员使用 `/draw` 开奖。

## 功能
- 群管理员交互式创建抽奖（标题、描述、报名截止、策略、预设中奖者）。
- 自动维护参与者列表、开奖日志。
- 支持随机抽奖与"先满足预设用户，再随机"的混合策略。
- MySQL 持久化，可部署在甲骨文云等任意 VPS。

## 依赖安装
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 环境变量
复制 `.env.example` 为 `.env` 并填入：

```
TELEGRAM_BOT_TOKEN=xxxx
GLOBAL_ADMIN_IDS=123456,987654
DATABASE_URL=mysql+aiomysql://user:password@host:3306/dbname
# WEBHOOK_URL=https://your.domain/telegram-webhook
# WEBHOOK_SECRET=optional-secret
```

> `DATABASE_URL` 使用 SQLAlchemy Async URL，驱动为 `aiomysql`。MySQL 数据库需提前创建好并授予权限。

## 初始化数据库
首次启动前无需额外操作，程序在运行时会自动执行 `init_db()` 并创建缺失的表；只需保证数据库可连通且账号具备建表权限。

## 运行机器人
默认采用 Long Polling：
```bash
python -m bot.main
```
若配置了 `WEBHOOK_URL`（需公网 HTTPS）：
1. 确保网关 443 端口指向 bot 程序所在 VPS。
2. 准备 TLS（可用 Nginx/Traefik 反代）。
3. 在 `.env` 中设置 `WEBHOOK_URL` 与可选的 `WEBHOOK_SECRET`。
4. 启动 `python -m bot.main`，程序会自动进入 webhook 模式。

建议用 `systemd`/`pm2`/`docker-compose` 做常驻守护，这里提供 systemd 示例：
```
[Unit]
Description=Telegram Lottery Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/choujiang
Environment="PYTHONUNBUFFERED=1"
ExecStart=/opt/choujiang/.venv/bin/python -m bot.main
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## 指令
| 指令 | 使用者 | 说明 |
| --- | --- | --- |
| `/start` | 所有人 | 介绍机器人功能 |
| `/help` | 所有人 | 查看帮助 |
| `/newlottery` | 群管理员 | 进入抽奖配置流程 |
| `/join` | 群成员 | 报名当前抽奖 |
| `/status` | 所有人 | 查看当前抽奖状态 |
| `/draw` | 群管理员 | 立即开奖 |
| `/cancel` | 群管理员 | 在配置流程中取消 |

## 流程概览
1. 群管理员执行 `/newlottery`，回答标题/描述/人数/截止时间/策略/预设中奖者。
2. 成功创建后，群成员使用 `/join` 报名。
3. 管理员 `/draw` 开奖，机器人优先满足预设用户，然后随机抽取剩余名额并公布结果。

## 后续可扩展
- 接入更复杂的抽奖策略（权重、黑名单等）。
- Web 管理后台或 CLI 管理工具。
- 加入反刷/频控、报名问卷等功能。
- 使用 Alembic 维护数据库迁移。
