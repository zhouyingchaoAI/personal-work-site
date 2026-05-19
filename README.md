# 个人工作报告邮件助手

这个本地网站会自动读取上级目录里的 `周报` 文件夹，识别最新周报和最新出差报告，生成邮件主题、正文，并把报告文件作为附件发送。

项目已拆分为前后端分离、按模块组织的结构：

- 后端入口：`app.py`
- 后端模块：`backend/`，按配置用户、报表、邮件、Skill/Agent、日记、论坛、资讯、文档生成、HTTP 服务拆分
- 前端入口：`frontend/index.html`
- 前端脚本模块：`frontend/js/`
- 前端样式模块：`frontend/css/`，由 `frontend/styles.css` 聚合
- 前端配置：`frontend/config.js`，单独部署前端时可配置后端 API 地址

现在也支持按引导表单新建标准文件：

- 周报：复制最近的 `.xlsx` 周报模板，写入“本周工作总结 / 重点工作跟进 / 下周工作计划”
- 出差报告：复制最近的 `.docx` 出差报告模板，写入报告人、部门、地点、时间、目的、行程、详情、问题、建议
- 新生成的文件会放到 `generated` 文件夹，并自动设为当前邮件附件

## 启动

```bash
cd /Users/zhouyingchao/Documents/codex/personal-work-site
python3 app.py
```

打开：

```text
http://127.0.0.1:8765
```

也可以使用英文相对地址：

```text
/personal-office-assistant
http://127.0.0.1:8765/personal-office-assistant
```

## 邮箱配置

复制一份配置文件：

```bash
cp config.example.json config.json
```

然后把 `config.json` 里的邮箱信息改成自己的。建议使用邮箱的 SMTP 授权码，不要使用网页登录密码。

也可以用环境变量配置：

```bash
export SMTP_HOST=smtp.example.com
export SMTP_PORT=587
export SMTP_USER=your-email@example.com
export SMTP_PASSWORD=your-smtp-authorization-code
export SMTP_FROM=your-email@example.com
python3 app.py
```

如果没有配置 SMTP，点击发送时不会真的发出邮件，会在 `drafts` 文件夹里生成 `.eml` 邮件草稿。

## 文件规则

- 周报：文件名包含 `工作周报`，格式为 `.xlsx` 或 `.xls`
- 出差报告：文件名以 `出差报告` 开头，格式为 `.docx` 或 `.md`
- 附件会使用 `周报` 文件夹里的原始文件

## 部署

### 方式一：直接后台运行（推荐本地/测试）

```bash
./start.sh
```

停止：

```bash
kill $(cat app.pid)
```

### 方式二：macOS 开机自启

```bash
cp deploy/com.personal.work-site.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.personal.work-site.plist
launchctl start com.personal.work-site
```

查看日志：

```bash
tail -f app.log
```

### 方式三：Linux 服务器（systemd）

```bash
sudo cp deploy/personal-work-site.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable personal-work-site
sudo systemctl start personal-work-site
```

查看状态：

```bash
sudo systemctl status personal-work-site
```

### 方式四：Docker（可选）

```bash
docker build -t personal-work-site .
docker run -d -p 8765:8765 -v $(pwd)/config.json:/app/config.json personal-work-site
```
