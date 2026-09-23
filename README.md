# StoreApp · 密钥与密码本地存储

一款纯本地运行的桌面小工具，用于集中保存大模型 API Key、网站账号密码等敏感信息。
不联网、不依赖数据库服务，数据保存在本地 SQLite 文件中。

## 功能

- **分组分类**：自定义分组（如「大模型 API」「社交账号」「服务器」），支持新增、重命名、删除分组；删除分组时其中的记录自动归入「未分组」
- **记录增删改查**：每条记录包含 名称 / 分组 / 账号 / 密钥·密码 / 标签 / 网址 / 备注；卡片式列表，悬停卡片即可 编辑 / 删除，点击卡片选中后也可用工具栏与 `Delete` 键
- **搜索与标签**：支持中英文逗号分隔的多标签；搜索框对 名称/账号/网址/备注/标签/分组名 做跨分组实时检索（大小写不敏感，`Esc` 清除，`Ctrl+K` / `Ctrl+F` 聚焦）
- **一键复制**：卡片悬停出现「复制」按钮，复制成功后按钮短暂变为绿色对勾「已复制」；账号旁有小复制图标；**30 秒后自动清空剪贴板**（期间你复制了别的内容则不会被误清；关闭程序时也会清理残留）
- **加密备份**：入口在右上角 ⚙ 设置菜单，一键导出 `.sab` 加密备份文件（PBKDF2 20万轮 + AES-256-GCM），导入支持「合并去重」或「覆盖全部」两种方式
- **密钥打码**：卡片默认显示圆点，单条眼睛图标切换显隐；⚙ 菜单可全局「显示密钥」
- **极简浅色界面**：顶栏 + 分组边栏 + 卡片列表布局，参考 Linear / Raycast 设计语言（圆角、轻阴影、150ms 过渡、复制反馈、空状态引导）
- **快捷操作**：`Ctrl+N` 新增，`Delete` 删除选中，`Ctrl+K`/`Ctrl+F` 搜索，`Esc` 清除搜索

## 运行（开发环境）

```bash
conda activate evTest              # Python 3.9，亦兼容 ev1ch 的 3.8
cd StoreApp
pip install -r requirements.txt    # pywebview（界面）+ cryptography（加密备份）
python main.py
```

界面由程序自带窗口内的本地网页渲染（pywebview → Edge WebView2，Win10/11 随 Edge 自带运行时），
**完全离线**：不打开浏览器、不联网，HTML/CSS/JS 随 exe 一起打包。

## 打包为 exe

```bash
conda activate evTest
python -m pip install -r requirements.txt   # 含 pyinstaller，仅首次
```

打包参数较多（需收集网页资源与 WebView2 依赖），**推荐直接双击 `build_exe.bat`**，
产物在 `dist/StoreApp.exe`（单文件，双击即可运行）。重复打包不会影响已有的 `data/` 数据文件。

## 目录结构

```
StoreApp/
├── main.py                     # 入口：pywebview 打开本地窗口加载内置界面
├── build_exe.bat               # 一键打包脚本（含资源/依赖收集参数）
├── requirements.txt            # pywebview + cryptography（运行）+ pyinstaller（打包）
├── data/storeapp.db            # 数据文件（已被 .gitignore 忽略）
└── storeapp/
    ├── __init__.py
    ├── db.py                   # SQLite 数据层：分组/记录 CRUD、搜索、备份导入导出
    ├── obfuscate.py            # secret 字段轻量混淆
    ├── backup.py               # .sab 加密备份读写（PBKDF2 + AES-256-GCM）
    ├── api.py                  # 暴露给界面的 API（pywebview js_api，错误统一为 {ok:false}）
    ├── clipboard.py            # Windows 剪贴板读写 + 30 秒自动清空（ctypes，不依赖 Tk）
    └── web/                    # 界面资源（开发直接读取，打包随 exe 收集）
        ├── index.html          # 页面骨架：顶栏 / 边栏 / 列表 / 弹窗容器
        ├── app.css             # 设计系统：#FAFAFA 背景、靛蓝 #6366F1、10px 圆角、150ms 过渡
        └── app.js              # 渲染与交互：分组/卡片/搜索/弹窗/备份流程（原生 JS，无构建）
```

## 数据存储位置

| 运行方式 | 数据文件位置 |
| --- | --- |
| `python main.py` | `StoreApp/data/storeapp.db` |
| `StoreApp.exe` | `StoreApp.exe 同级目录/data/storeapp.db` |

## 备份文件说明

- 格式：`MAGIC | salt(16B) | nonce(12B) | AES-256-GCM(ciphertext)`，扩展名 `.sab`；
- 密码由你在导出时输入，**不保存在任何地方，遗忘即该备份无法恢复**；
- 密码错误或文件被改动会明确报错，不会导入脏数据；
- 导入前会先展示备份内容（分组数/记录数/导出时间），由你选择「合并」或「覆盖」。

## ⚠️ 安全说明（请务必阅读）

当前库文件按需求采用 **本地明文 + 轻量混淆** 存储（升级方案见 [docs/master-password-design.md](docs/master-password-design.md)）：

- `secret` 字段写入数据库前经过混淆（XOR + Base64），防止他人随手打开文件直接看到；
- **混淆不是加密**：混淆钥写在源码里，能被逆向还原。任何人拿到 `storeapp.db` + 源码即可还原全部密钥；
- 因此：**不要把 `data/` 目录（已在 `.gitignore` 中忽略）上传到任何仓库或云盘**；
- 与之相对，`.sab` 备份文件是真加密（AES-256-GCM），可以安全地拷贝到 U 盘/网盘保存，只要密码足够强。

## 推送到 GitHub

```bash
cd StoreApp
git remote add origin https://github.com/<你的用户名>/StoreApp.git
git push -u origin main
```

`.gitignore` 已排除 `data/`、`dist/`、`build/`、`*.spec`、`__pycache__`，密钥数据不会被提交。

## 路线图

| # | 规划项 | 状态 |
| --- | --- | --- |
| 1 | 主密码 + AES-GCM 加密（仅 secret 字段） | ⏸ **暂不实施**：以简单易用优先，保持"打开即用"；方案文档留作日后参考 [docs/master-password-design.md](docs/master-password-design.md) |
| 2 | 一键复制 + 自动清空剪贴板 | ✅ v1.1 |
| 3 | 搜索与标签 | ✅ v1.1 |
| 4 | 加密备份的导入/导出 | ✅ v1.1 |
| 5 | 空闲自动锁定 + 手动锁库 | ⏸ 随第 1 项一并搁置 |
| 6 | 界面重构：pywebview 本地窗口 + 极简浅色设计系统（Linear/Raycast 风格） | ✅ v1.2 |
