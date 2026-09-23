**简体中文** | [English](README_EN.md)

<div align="center">

# KeyV

**KeyV, your local vault.**

一款纯本地、完全离线的桌面保险库：集中保存你的 API Key、账号密码与服务器凭据。

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows-0078D4?style=flat)
![Offline](https://img.shields.io/badge/offline-100%25-44CC11?style=flat)
![Version](https://img.shields.io/badge/version-1.2.0--beta.1-6366F1?style=flat)

</div>

## ✨ 功能特性

- **分组分类** —— 自定义分组（如「大模型 API」「服务器」「社交账号」），支持新增 / 重命名 / 删除；删除分组后其中的记录自动归入「未分组」
- **卡片式记录管理** —— 每条记录包含 名称 / 分组 / 账号 / 密钥·密码 / 标签 / 网址 / 备注；悬停卡片即可编辑、删除，点击卡片选中后也可用工具栏或 `Delete` 键操作
- **全局搜索与标签** —— 对 名称 / 账号 / 网址 / 备注 / 标签 / 分组名 跨分组实时检索（大小写不敏感）；支持多标签（中英文逗号分隔），边栏计数随关键词联动
- **一键复制，自动清空** —— 悬停卡片复制密钥、账号旁图标复制账号，按钮变绿色「✓ 已复制」；**30 秒后自动清空剪贴板**（期间你复制了其他内容不会被误清，退出程序也会清理残留）
- **加密备份** —— ⚙ 菜单一键导出 `.sab` 加密备份（PBKDF2 20 万轮 + AES-256-GCM）；导入前可预览备份内容，支持「合并去重」或「覆盖全部」
- **密钥打码** —— 卡片默认显示圆点，单条眼睛图标切换明文显隐；⚙ 菜单可全局「显示密钥」
- **极简浅色界面** —— 顶栏 + 分组边栏 + 卡片列表布局，参考 Linear / Raycast 设计语言（10px 圆角、轻阴影、150ms 过渡、空状态插画引导）
- **纯本地离线** —— 数据保存在本地 SQLite 文件；不联网、不打开浏览器、无遥测上报

## 🚀 快速开始

**环境要求**：Windows 10 / 11（自带 Edge WebView2 运行时）· Python 3.8+

```bash
git clone 
cd KeyV
pip install -r requirements.txt
python main.py
```

### 打包为单文件 exe

```bash
build_exe.bat
```

产物为 `dist/StoreApp.exe`（单文件、无控制台窗口），双击即可运行，无需安装。
重复打包不会影响已有的 `data/` 数据文件。

## 📖 使用说明

**界面布局**

- **顶栏**：Logo 与名称 · 圆角全局搜索框（`Ctrl K` 提示）· ⚙ 设置菜单
- **侧边栏**：全部记录 / 未分组 / 自定义分组，每项带数量徽章；底部「新增分组」
- **主区**：工具栏（编辑 / 删除 / 新增记录）+ 卡片列表；卡片含分组色块头像、名称、账号、标签胶囊与密钥圆点

**快捷键**

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl/Cmd + K` · `Ctrl/Cmd + F` | 聚焦搜索框 |
| `Ctrl/Cmd + N` | 新增记录 |
| `Delete` | 删除选中的卡片 |
| `Esc` | 清除搜索 / 关闭弹窗 |

**设置菜单（⚙）**：显示密钥（全局切换）· 导出加密备份 · 导入备份 · 版本号与数据库路径

## 💾 数据与备份

**数据存储位置**

| 运行方式 | 数据文件位置 |
| --- | --- |
| `python main.py` | `<项目目录>/data/storeapp.db` |
| `StoreApp.exe` | `<exe 所在目录>/data/storeapp.db` |

**`.sab` 备份文件**

- 格式：`MAGIC | salt(16B) | nonce(12B) | AES-256-GCM(ciphertext)`，扩展名 `.sab`
- 密码由你在导出时输入，**不保存在任何地方，遗忘即该备份无法恢复**
- 密码错误或文件被篡改会明确报错，绝不导入脏数据
- 导入前先展示备份内容（分组数 / 记录数 / 导出时间），由你选择「合并」或「覆盖」

## 🔒 安全说明

当前库文件按设计采用 **本地明文 + 轻量混淆** 存储（存储加密的方案设计见 [docs/master-password-design.md](docs/master-password-design.md)，当前未启用）：

- `secret` 字段写库前经过混淆（XOR + Base64），防止他人随手打开文件直接看到
- **混淆不是加密**：混淆钥随源码分发，可被逆向还原；任何人拿到 `storeapp.db` + 源码即可还原全部密钥
- 因此请**不要把 `data/` 目录上传到任何仓库或云盘**
- 与之相对，`.sab` 备份文件是真加密（AES-256-GCM），只要密码足够强，可安全拷贝到 U 盘 / 网盘

## ⚠️ 免责声明

> 本软件按原样提供，作者不对因使用本软件导致的密钥泄露等问题承担责任。

## 🗂 项目结构

```
KeyV/
├── main.py                        # 入口：pywebview 打开本地窗口加载内置界面
├── build_exe.bat                  # 一键打包脚本（含资源/依赖收集参数）
├── requirements.txt               # pywebview + cryptography（运行）+ pyinstaller（打包）
├── docs/
│   └── master-password-design.md  # 存储加密方案设计文档（当前未启用）
├── data/storeapp.db               # 数据文件（运行时生成，已被 .gitignore 忽略）
└── storeapp/
    ├── __init__.py
    ├── db.py                      # SQLite 数据层：分组/记录 CRUD、搜索、迁移
    ├── obfuscate.py               # secret 字段轻量混淆
    ├── backup.py                  # .sab 加密备份读写（PBKDF2 + AES-256-GCM）
    ├── api.py                     # 暴露给界面的 API（pywebview js_api，错误统一为 {ok:false}）
    ├── clipboard.py               # Windows 剪贴板读写 + 30 秒自动清空（ctypes）
    └── web/                       # 界面资源（开发直接读取，打包随 exe 收集）
        ├── index.html             # 页面骨架：顶栏 / 边栏 / 列表 / 弹窗容器
        ├── app.css                # 设计系统：#FAFAFA 背景、靛蓝 #6366F1、10px 圆角、150ms 过渡
        └── app.js                 # 渲染与交互：分组/卡片/搜索/弹窗/备份流程（原生 JS，无构建）
```

## 🛠 技术栈

| 层 | 技术 |
| --- | --- |
| 窗口 | [pywebview](https://pywebview.flowrl.com/)（原生窗口）+ Edge WebView2 离线渲染 |
| 前端 | 原生 HTML / CSS / JavaScript，无框架、无构建链 |
| 存储 | SQLite（Python 内置 `sqlite3`）+ secret 字段轻量混淆 |
| 加密 | [cryptography](https://cryptography.io/)：PBKDF2-HMAC-SHA256（200,000 轮）+ AES-256-GCM |
| 剪贴板 | Win32 API（`ctypes`），复制后 30 秒自动清空 |
| 打包 | [PyInstaller](https://pyinstaller.org/)（单文件、无控制台） |

## 📄 License

本项目以 [MIT License](LICENSE) 开源（Copyright © 2026 hyc031）。
