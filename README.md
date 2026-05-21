# 个人智能办公助手

这是一个本地优先的个人智能办公工作台。它把周报、出差报告、邮件、工作日记、每日资讯、金点子论坛和悬浮智能体集中到同一个 Web 应用里，适合个人或小团队在内网/本机环境中使用。

## 主要能力

- 周报助手：填写本周工作总结、重点跟进和下周计划，按标准 Excel 模板生成周报。
- 出差报告助手：维护出差地点、时间、目的、行程、过程记录和结论，按标准 Word 模板生成出差报告。
- 邮件发送：为周报和出差报告生成邮件草稿，自动带出当前账号的收件人、抄送和邮件签名。
- 普通邮件处理：读取收件箱、查看邮件详情、撰写邮件并发送附件。
- 工作日记：记录每日工作，可用于后续整理周报素材。
- 每日资讯：配置资讯源和搜索关键词，生成并保存历史资讯。
- 金点子论坛：发布话题、评论、点赞，沉淀团队想法。
- 悬浮智能体：在页面内对话式处理周报、出差报告、日记、邮件和历史查询。
- 多用户：每个账号拥有独立资料、邮件配置、签名、草稿、历史报告和临时生成文件。

## 项目结构

- `app.py`：后端启动入口。
- `backend/`：后端功能模块，包括用户配置、报告生成、邮件、Agent、日记、论坛、资讯、Skill 和 HTTP 服务。
- `frontend/index.html`：前端页面入口。
- `frontend/js/`：前端交互模块。
- `frontend/css/`：前端样式模块，由 `frontend/styles.css` 聚合。
- `frontend/config.js`：前端部署配置，可设置 API 地址和相对路径。
- `user_data/`：用户数据目录，按账号隔离保存资料、报告、草稿、日记和邮件缓存。

## 报告文件规则

每个用户的周报和出差报告分开存储：

- 临时周报：`user_data/<用户名>/generated/weekly/`
- 临时出差报告：`user_data/<用户名>/generated/trip/`
- 历史周报：`user_data/<用户名>/reports/weekly/`
- 历史出差报告：`user_data/<用户名>/reports/trip/`

点击“按标准模板生成文件”时，文件会先进入临时目录。只有邮件成功发送后，才会移动到对应历史目录。同日期同文件名会直接覆盖，不再追加 `-生成1` 这类后缀。

如果平台没有任何历史周报或出差报告，系统会使用内置基础模板生成第一份文件。之后新文件会继续沿用最近的历史报告格式。

文件识别规则：

- 周报：文件名包含 `工作周报`，格式为 `.xlsx` 或 `.xls`。
- 出差报告：文件名以 `出差报告` 开头，格式为 `.docx` 或 `.md`。

## 启动

```bash
cd /Users/zhouyingchao/Documents/codex/personal-work-site
python3 app.py
```

打开：

```text
http://127.0.0.1:8765
```

也可以使用相对访问地址：

```text
http://127.0.0.1:8765/personal-office-assistant
```

## 配置

首次使用可以复制示例配置：

```bash
cp config.example.json config.json
```

系统支持在页面中配置：

- 用户账号和中文名
- 每个用户的发件邮箱、SMTP/IMAP 账号
- 周报收件人和抄送
- 出差报告收件人和抄送
- 每个用户自己的邮件签名
- AI 接口地址、模型和提示词
- 每日资讯源和搜索配置

建议使用邮箱 SMTP/IMAP 授权码，不要使用网页登录密码。

如果某个账号没有配置 SMTP，发送时不会真的发出邮件，会在该用户的 `drafts` 目录生成 `.eml` 草稿。

## 部署

本地后台运行：

```bash
./start.sh
```

停止：

```bash
kill $(cat app.pid)
```

macOS 开机自启：

```bash
cp deploy/com.personal.work-site.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.personal.work-site.plist
launchctl start com.personal.work-site
```

查看日志：

```bash
tail -f app.log
```

Linux systemd：

```bash
sudo cp deploy/personal-work-site.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable personal-work-site
sudo systemctl start personal-work-site
```

Docker：

```bash
docker build -t personal-work-site .
docker run -d -p 8765:8765 -v $(pwd)/config.json:/app/config.json personal-work-site
```

## 测试

```bash
PYTHONPYCACHEPREFIX=/tmp/pws-pycache python3 -m unittest discover -s tests/unit -p 'test_*.py' -v
```
