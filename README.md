# StoreApp · 密钥与密码本地存储

一款纯本地运行的桌面小工具，用于集中保存大模型 API Key、网站账号密码等敏感信息。
不联网、不依赖数据库服务，数据保存在本地 SQLite 文件中。

## 功能

- **分组分类**：自定义分组（如「大模型 API」「社交账号」「服务器」），支持新增、重命名、删除分组；删除分组时其中的记录自动归入「未分组」
- **记录增删改查**：每条记录包含 名称 / 分组 / 账号 / 密钥·密码 / 网址 / 备注 / 更新时间
- **表格浏览**：按分组筛选，密钥默认打码，可勾选「显示密钥」查看
- **快捷操作**：双击记录编辑，右键菜单编辑/删除，`Delete` 删除，`Ctrl+N` 新增

## 运行（开发环境）

```bash
conda activate evTest          # Python 3.9，亦兼容 ev1ch 的 3.8
cd StoreApp
python main.py
```

> 运行时只用到标准库 `tkinter` / `sqlite3`，无需 `pip install` 任何依赖。

## 打包为 exe

```bash
conda activate evTest
python -m pip install pyinstaller     # 仅首次
python -m PyInstaller --noconfirm --onefile --windowed --name StoreApp main.py
```

或直接双击 `build_exe.bat`，产物在 `dist/StoreApp.exe`（单文件，双击即可运行）。

## 目录结构

```
StoreApp/
├── main.py                     # 入口
├── build_exe.bat               # 一键打包脚本
├── requirements.txt            # 仅打包需要 pyinstaller
├── data/storeapp.db            # 数据文件（已被 .gitignore 忽略）
└── storeapp/
    ├── __init__.py
    ├── db.py                   # SQLite 数据层：分组 + 记录 CRUD
    ├── obfuscate.py            # secret 字段轻量混淆
    └── ui/
        ├── main_window.py      # 主窗口
        └── dialogs.py          # 记录/分组对话框
```

## 数据存储位置

| 运行方式 | 数据文件位置 |
| --- | --- |
| `python main.py` | `StoreApp/data/storeapp.db` |
| `StoreApp.exe` | `StoreApp.exe 同级目录/data/storeapp.db` |

## ⚠️ 安全说明（请务必阅读）

当前版本按需求采用 **本地明文 + 轻量混淆** 存储：

- `secret` 字段写入数据库前经过混淆（XOR + Base64），防止他人随手打开文件直接看到；
- **混淆不是加密**：混淆钥写在源码里，能被逆向还原。任何人拿到 `storeapp.db` + 源码即可还原全部密钥；
- 因此：**不要把 `data/` 目录（已在 `.gitignore` 中忽略）上传到任何仓库或云盘**。

如需真正的安全性，后续可升级为「主密码 + AES-256-GCM 加密」，见下文规划。

## 推送到 GitHub

```bash
cd StoreApp
git init
git add .
git commit -m "StoreApp v1.0: 本地密钥/密码存储（分组 + 增删改查）"
git remote add origin https://github.com/<你的用户名>/StoreApp.git
git push -u origin main
```

`.gitignore` 已排除 `data/`、`dist/`、`build/`、`*.spec`、`__pycache__`，密钥数据不会被提交。

## 后续规划（建议优先级）

1. **主密码 + AES-GCM 加密**：启动输入主密码派生密钥，数据库文件被拷走也无法解密
2. 一键复制到剪贴板（带 N 秒后自动清空）
3. 搜索与标签
4. 加密备份的导入/导出
5. 主密码修改与空闲自动锁定
