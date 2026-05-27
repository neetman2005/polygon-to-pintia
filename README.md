# Polygon → Pintia 测试数据转换工具

将 [Polygon](https://polygon.codeforces.com) 出题平台的测试数据自动转换为 [Pintia（PTA）](https://pintia.cn) 兼容格式。

---

## 📖 完整工作流程

### 前置步骤：在 Polygon 中导出题目

1. 在 [Polygon](https://polygon.codeforces.com) 中完成所有题目的出题工作
2. 对每道题目，依次点击 **Create Package** → 选择 **Full** → 点击 **Continue**
3. 在下载页面点击 **Windows** 或 **Linux** 按钮，下载对应的压缩包

> 下载得到的压缩包命名格式为 `{problem}-{version}$windows.zip` 或 `{problem}-{version}$linux.zip`，其中 `version` 为任意正整数，`problem` 为题目名称。

### 操作步骤：使用本工具转换

1. 启动 `PolygonToPintia.exe`（或将压缩包**拖拽**到程序窗口）
2. 在程序窗口中**选择**或**拖入**从 Polygon 下载的压缩包
3. 程序自动处理，完成后会展示两类结果：
   - **📦 测试数据压缩包**（`-tests-pintia.zip`）
   - **📝 题面 Markdown 文件**（`-english-problem.md` / `-chinese-problem.md` 等）
4. 每种文件都有独立的 **📥 下载** 和 **🗑 删除** 按钮

### 后续步骤：上传至 Pintia

1. 登录 [Pintia](https://pintia.cn) 平台
2. 将转换后的 `-tests-pintia.zip` 上传为测试数据
3. 将转换后的题面 `.md` 文件内容粘贴到 Pintia 的题目描述中

---

## 🚀 快速开始

### 方式一：下载 exe（推荐，无需安装 Python）

1. 前往 [Releases](../../releases) 页面下载最新版 `PolygonToPintia.exe`
2. 将 exe 拷贝到任意目录，双击运行
3. 拖拽 Polygon Full 压缩包到窗口，或点击「选择文件」按钮
4. 点击 **📥 下载** 保存转换结果

### 方式二：从源码运行

```bash
git clone https://github.com/<your-username>/polygonToPintia.git
cd polygonToPintia
pip install -r requirements.txt
python main.py
```

## 📋 功能说明

| 功能 | 说明 |
|------|------|
| **导入** | 拖拽 `.zip` 文件到窗口，或点击「选择文件」按钮 |
| **测试数据转换** | 自动查找 `tests/` 文件夹，生成 `-tests-pintia.zip` |
| **题面转换** | 自动查找 `statements/*/problem.tex`，转为 Markdown `.md` 文件 |
| **下载** | 每种文件有独立的下载按钮（**复制**，临时文件保留） |
| **删除** | 每种文件有独立的删除按钮 |

### 测试数据转换规则

- 输入文件 `{id}` → `{id}.in`（Unix 换行, UTF-8）
- 输出文件 `{id}.a` → `{id}.out`（Unix 换行, UTF-8）
- 生成文件名：`{原压缩包名}-tests-pintia.zip`

### 题面转换规则（LaTeX → Markdown）

| LaTeX | Markdown |
|-------|----------|
| `\textbf{...}` | `**...**` |
| `\textit{...}` / `\emph{...}` | `*...*` |
| `\texttt{...}` | `` `...` `` |
| `\text{...}`（非数学模式） | `**...**` |
| `\begin{itemize}...\end{itemize}` | `* ` 无序列表 |
| `\begin{enumerate}...\end{enumerate}` | `1. ` 有序列表 |
| `\section{...}` | `## ...` |
| `\subsection{...}` | `### ...` |
| `$...$` / `$$...$$` | 原样保留 |

> 数学模式（`$...$`）内的 LaTeX 命令原样保留，不做转换。

- 题面文件命名：`{原压缩包名}-{语言}-problem.md`
- 临时文件存放在 exe 同级目录的 `temp/` 文件夹

### 校验与警告

程序会自动检测并提示：

| 检测项 | 行为 |
|--------|------|
| 无 `tests/` 文件夹 | ❌ 报错，停止处理 |
| 文件名不符合 `{id}` 或 `{id}.a` 格式 | ⚠️ 警告，忽略该文件 |
| 某 ID 只有输入无输出（或反之） | ⚠️ 警告，仅导出存在的一方 |
| ID 不连续、不从 1 开始、非正整数 | ⚠️ 警告，继续处理 |

### 文件生命周期

| 操作 | temp 中的文件 |
|------|-------------|
| 导入新压缩包 | 上一个**未下载**的文件自动删除；**已下载**的保留 |
| 下载文件 | **复制**到选择位置，temp 中保留原文件 |
| 删除文件 | 直接删除 temp 中的文件 |
| 关闭程序 | 弹窗确认后，**清空**整个 temp 目录 |

## 📁 项目结构

```
polygonToPintia/
├── main.py              # 程序入口
├── app.py               # GUI 界面（tkinter）
├── processor.py         # 核心处理逻辑（测试数据 + 题面）
├── tex_converter.py     # LaTeX → Markdown 转换引擎
├── requirements.txt     # Python 依赖
├── build.bat            # 打包脚本（生成 .exe）
├── LICENSE              # MIT 许可
└── temp/                # 运行时临时目录（自动创建，已 gitignore）
```

## 🔧 自行打包

修改代码后，运行以下命令重新生成 exe：

```bash
pip install -r requirements.txt pyinstaller
python -m PyInstaller --onefile --windowed --hidden-import tkinterdnd2 --name "PolygonToPintia" main.py
```

生成的文件在 `dist/PolygonToPintia.exe`。或直接双击运行 `build.bat`。

## ❓ 常见问题

**Q: 拖拽文件没反应？**  
A: 使用「选择文件」按钮加载压缩包，或确保 `tkinterdnd2` 已正确安装。

**Q: 支持哪些编码？**  
A: 自动检测 UTF-8（含 BOM）、GBK/GB2312/GB18030、Latin-1 等，统一转为 UTF-8 + LF 换行。

**Q: 压缩包不支持？**  
A: 请确认压缩包是 Polygon 的 **Full Package**（Create package → Full → Download），不是 Standard package。

**Q: 题面转换后格式不对？**  
A: 本工具处理常见的 LaTeX 标记（粗体、斜体、列表、章节等）。数学公式（`$...$`）原样保留，Pintia 平台支持 LaTeX 数学渲染。如果遇到未处理的 LaTeX 命令，请反馈以便完善。

**Q: 题面预览显示乱码？**  
A: 预览仅做参考，已去除 Markdown 标记以方便阅读。请下载 `.md` 文件后在任何 Markdown 查看器（VS Code、Typora 等）中查看完整效果。

**Q: 临时文件在哪里？**  
A: exe 同级目录的 `temp/` 文件夹。程序退出时会自动清理。

## 📄 许可

MIT License — 详见 [LICENSE](LICENSE) 文件。
