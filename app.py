"""
Polygon to Pintia - GUI 应用程序

提供拖拽和文件选择界面，处理 Polygon 完整包并生成 Pintia 格式的测试数据。
"""

import os
import sys
import math
import shutil
import atexit
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# 尝试导入 tkinterdnd2 以支持拖拽
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
    TkinterDnD = tk.Tk
    DND_FILES = None

from processor import (
    process_polygon_zip,
    format_file_size,
    ProcessingWarning,
)


class _FileCard(ttk.Frame):
    """单个生成文件的展示卡片（带下载/删除按钮）"""
    
    def __init__(self, parent, app, icon, title, subtitle, filepath, filename,
                 ext=".zip", preview=None, **kwargs):
        super().__init__(parent, padding=8, relief=tk.GROOVE, borderwidth=1, **kwargs)
        self.app = app
        self.filepath = filepath
        self.filename = filename
        self.ext = ext
        
        # 图标
        self.icon_label = ttk.Label(self, text=icon, font=("Segoe UI", 18))
        self.icon_label.pack(side=tk.LEFT, padx=(0, 10))
        
        # 信息
        info_frame = ttk.Frame(self)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(info_frame, text=title, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(info_frame, text=subtitle, font=("Segoe UI", 8),
                  foreground="#6C757D").pack(anchor=tk.W)
        
        # 预览区域（如果有）
        if preview:
            preview_frame = ttk.Frame(self)
            preview_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0), padx=(28, 0))
            
            preview_text = tk.Text(
                preview_frame,
                height=5,
                wrap=tk.WORD,
                font=("Consolas", 8),
                relief=tk.FLAT,
                bg="#F8F9FA",
                fg="#495057",
                padx=6,
                pady=4,
            )
            preview_text.insert("1.0", preview)
            preview_text.config(state=tk.DISABLED)
            preview_text.pack(fill=tk.BOTH, expand=True)
        
        # 按钮
        btn_frame = ttk.Frame(self)
        btn_frame.pack(side=tk.RIGHT, padx=(10, 0))
        
        ttk.Button(
            btn_frame, text="📥 下载",
            command=lambda: self.app.download_generated_file(
                self.filepath, self.filename, self.ext
            )
        ).pack(side=tk.LEFT, padx=(0, 5))
        
        ttk.Button(
            btn_frame, text="🗑 删除",
            command=lambda: self.app.delete_generated_file(
                self.filepath, os.path.basename(self.filepath)
            )
        ).pack(side=tk.LEFT)


class ResultFrame(ttk.LabelFrame):
    """处理结果展示区域（测验压缩包 + 题面文件卡片）"""
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, text="处理结果", padding=10, **kwargs)
        self.app = app
        self._file_cards = []  # 存放所有 _FileCard 实例
        self._setup_ui()
    
    def _setup_ui(self):
        # 可滚动的画布
        self.canvas = tk.Canvas(self, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 警告区域
        self.warning_frame = ttk.Frame(self.scrollable_frame)
        self.warning_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.warning_text = tk.Text(
            self.warning_frame,
            height=3,
            wrap=tk.WORD,
            font=("Segoe UI", 9),
            relief=tk.FLAT,
            bg="#FFF3CD",
            fg="#856404",
            padx=8,
            pady=4,
            state=tk.DISABLED,
        )
        self.warning_text.pack(fill=tk.X)
        
        # 测试文件列表（Treeview）
        self.list_frame = ttk.LabelFrame(self.scrollable_frame, text="📦 测试文件列表", padding=5)
        self.list_frame.pack(fill=tk.X, pady=(0, 10))
        
        columns = ("id", "input", "input_size", "output", "output_size")
        self.tree = ttk.Treeview(
            self.list_frame,
            columns=columns,
            show="headings",
            height=6,
            selectmode=tk.NONE,
        )
        
        self.tree.heading("id", text="ID")
        self.tree.heading("input", text="输入文件")
        self.tree.heading("input_size", text="大小")
        self.tree.heading("output", text="输出文件")
        self.tree.heading("output_size", text="大小")
        
        self.tree.column("id", width=50, anchor=tk.CENTER)
        self.tree.column("input", width=130)
        self.tree.column("input_size", width=70, anchor=tk.CENTER)
        self.tree.column("output", width=130)
        self.tree.column("output_size", width=70, anchor=tk.CENTER)
        
        tree_scrollbar = ttk.Scrollbar(self.list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tree_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 测试 zip 文件卡片
        self.test_zip_card_frame = ttk.Frame(self.scrollable_frame)
        self.test_zip_card_frame.pack(fill=tk.X, pady=(0, 5))
        
        # 题面文件卡片容器
        self.statements_frame = ttk.LabelFrame(
            self.scrollable_frame, text="📝 题面文件 (Markdown)", padding=5
        )
        self.statements_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.statements_inner = ttk.Frame(self.statements_frame)
        self.statements_inner.pack(fill=tk.X)
        
        # 初始隐藏
        self.pack_forget()
    
    def _on_canvas_configure(self, event):
        """画布大小变化时调整内部框架宽度"""
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def show_result(self, result: dict):
        """显示处理结果"""
        # 清理旧的卡片
        for card in self._file_cards:
            card.destroy()
        self._file_cards.clear()
        
        # 清理语句区域
        for child in self.statements_inner.winfo_children():
            child.destroy()
        
        # 警告信息
        self.warning_text.config(state=tk.NORMAL)
        self.warning_text.delete("1.0", tk.END)
        
        has_warnings = any(w.level == 'warning' for w in result['warnings'])
        has_errors = any(w.level == 'error' for w in result['warnings'])
        
        if has_warnings or has_errors:
            warning_msgs = []
            for w in result['warnings']:
                if w.level in ('warning', 'error'):
                    warning_msgs.append(str(w))
            if warning_msgs:
                self.warning_text.insert("1.0", "\n".join(warning_msgs))
            else:
                self.warning_text.insert("1.0", "✅ 未发现任何警告")
        else:
            self.warning_text.insert("1.0", "✅ 未发现任何警告")
        
        self.warning_text.config(state=tk.DISABLED)
        
        # 测试文件列表
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        if result.get('test_summary'):
            for test in result['test_summary']:
                inp = test.get('input')
                out = test.get('output')
                
                inp_name = inp['new_name'] if inp else "\u2014"
                inp_size = format_file_size(inp['size']) if inp else "\u2014"
                out_name = out['new_name'] if out else "\u2014"
                out_size = format_file_size(out['size']) if out else "\u2014"
                
                self.tree.insert("", tk.END, values=(
                    test['id'],
                    inp_name,
                    inp_size,
                    out_name,
                    out_size,
                ))
        
        # 测试 zip 文件卡片（支持多分卷）
        for child in self.test_zip_card_frame.winfo_children():
            child.destroy()
        
        outputs = result.get('outputs', [])
        if not outputs and result.get('output_path'):
            # 兼容旧格式：单个 output_path
            outputs = [{
                'path': result['output_path'],
                'name': result['output_name'],
                'size': result['output_size'],
                'test_count': result['test_count'],
                'id_range': '',
            }]
        
        total_outputs = len(outputs)
        for out in outputs:
            size_str = format_file_size(out['size'])
            if total_outputs > 1:
                subtitle = f"大小: {size_str}  |  测试用例: {out['test_count']} 个  |  ID 范围: {out.get('id_range', '?')}"
            else:
                subtitle = f"大小: {size_str}  |  测试用例: {out['test_count']} 个"
            
            card = _FileCard(
                self.test_zip_card_frame, self.app,
                icon="📦",
                title=out['name'],
                subtitle=subtitle,
                filepath=out['path'],
                filename=out['name'],
                ext=".zip",
            )
            card.pack(fill=tk.X, pady=(0, 5))
            self._file_cards.append(card)
        
        # 题面文件卡片
        self.statements_frame.pack(fill=tk.X, pady=(0, 5))
        statements = result.get('statements', [])
        if statements:
            for stmt in statements:
                size_str = format_file_size(stmt['output_size'])
                subtitle = f"语言: {stmt['lang_display']}  |  大小: {size_str}"
                preview = stmt.get('preview', None)
                card = _FileCard(
                    self.statements_inner, self.app,
                    icon="📝",
                    title=stmt['output_name'],
                    subtitle=subtitle,
                    filepath=stmt['output_path'],
                    filename=stmt['output_name'],
                    ext=".md",
                    preview=preview,
                )
                card.pack(fill=tk.X, pady=(0, 5))
                self._file_cards.append(card)
        else:
            ttk.Label(
                self.statements_inner,
                text="（未找到题面文件）",
                font=("Segoe UI", 9),
                foreground="#6C757D",
            ).pack(pady=5)
        
        # 显示结果区域
        self.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
    
    def hide_result(self):
        """隐藏结果区域"""
        for card in self._file_cards:
            card.destroy()
        self._file_cards.clear()
        self.pack_forget()


class DropZone(ttk.Frame):
    """拖拽区域"""
    
    def __init__(self, parent, app, **kwargs):
        super().__init__(parent, padding=2, **kwargs)
        self.app = app
        
        self._setup_ui()
        
        # 注册拖拽
        if HAS_DND:
            try:
                self.drop_target_register(DND_FILES)
                self.dnd_bind('<<Drop>>', self._on_drop)
                self.dnd_bind('<<DragEnter>>', self._on_drag_enter)
                self.dnd_bind('<<DragLeave>>', self._on_drag_leave)
            except Exception:
                pass
    
    def _setup_ui(self):
        # 使用 Canvas 绘制虚线边框效果
        self.canvas = tk.Canvas(
            self,
            bg="#F8F9FA",
            highlightthickness=0,
            height=160,
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # 绑定重绘事件
        self.canvas.bind("<Configure>", self._on_resize)
        
        # 拖拽提示文字
        self.drop_text = self.canvas.create_text(
            0, 0,
            text="📦\n拖拽 Polygon Full 压缩包到此处\n或点击下方按钮选择文件",
            font=("Segoe UI", 12),
            fill="#6C757D",
            justify=tk.CENTER,
        )
        
        # 绑定点击事件
        self.canvas.bind("<Button-1>", lambda e: self.app.select_file())
        
        # 初始绘制边框
        self._draw_border()
    
    def _on_resize(self, event):
        """窗口大小变化时重绘"""
        self._draw_border()
        # 居中文字
        w = event.width
        h = event.height
        self.canvas.coords(self.drop_text, w // 2, h // 2)
    
    def _draw_border(self):
        """绘制虚线边框"""
        self.canvas.delete("border")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        if w > 10 and h > 10:
            # 绘制虚线矩形
            dash_pattern = (8, 4)
            x0, y0 = 8, 8
            x1, y1 = w - 8, h - 8
            
            # 使用多条短线模拟虚线
            self._draw_dashed_rect(x0, y0, x1, y1, dash_pattern, "#ADB5BD", 2)
    
    def _draw_dashed_rect(self, x0, y0, x1, y1, dash, color, width):
        """绘制虚线矩形"""
        # 上边
        self._draw_dashed_line(x0, y0, x1, y0, dash, color, width, "border")
        # 下边
        self._draw_dashed_line(x0, y1, x1, y1, dash, color, width, "border")
        # 左边
        self._draw_dashed_line(x0, y0, x0, y1, dash, color, width, "border")
        # 右边
        self._draw_dashed_line(x1, y0, x1, y1, dash, color, width, "border")
    
    def _draw_dashed_line(self, x0, y0, x1, y1, dash, color, width, tag):
        """绘制虚线"""
        dx = x1 - x0
        dy = y1 - y0
        length = math.sqrt(dx * dx + dy * dy)
        
        if length == 0:
            return
        
        ux = dx / length
        uy = dy / length
        
        pos = 0
        dash_idx = 0
        while pos < length:
            seg_len = dash[dash_idx % len(dash)]
            end = min(pos + seg_len, length)
            
            if dash_idx % 2 == 0:  # 实线段
                self.canvas.create_line(
                    x0 + pos * ux, y0 + pos * uy,
                    x0 + end * ux, y0 + end * uy,
                    fill=color, width=width, tags=tag,
                )
            
            pos = end
            dash_idx += 1
    
    def _on_drag_enter(self, event):
        """拖拽进入时高亮显示"""
        self.canvas.config(bg="#E8F0FE")
        self.canvas.itemconfig(self.drop_text, fill="#1A73E8")
    
    def _on_drag_leave(self, event):
        """拖拽离开时恢复"""
        self.canvas.config(bg="#F8F9FA")
        self.canvas.itemconfig(self.drop_text, fill="#6C757D")
    
    def _on_drop(self, event):
        """处理拖拽事件"""
        # 恢复颜色
        self._on_drag_leave(None)
        
        raw_data = event.data
        
        # tkinterdnd2 在 Windows 上返回的格式可能是:
        # 单文件: "C:\path\to\file.zip"
        # 多文件: "{C:\path\to\file1.zip} {C:\path\to\file2.zip}"
        # 或空格在路径中: "{C:\path with spaces\file.zip}"
        
        # 解析文件路径列表
        filepaths = []
        if raw_data:
            # 提取所有 {...} 包裹的路径
            import re
            matches = re.findall(r'\{(.+?)\}', raw_data)
            if matches:
                filepaths = matches
            else:
                # 没有大括号，直接使用
                filepath = raw_data.strip().strip('"').strip("'")
                if filepath:
                    filepaths = [filepath]
        
        if not filepaths:
            return
        
        # 只取第一个文件
        filepath = filepaths[0]
        
        if os.path.isfile(filepath):
            self.app.process_file(filepath)
        else:
            messagebox.showwarning("无效文件", f"无法找到文件:\n{filepath}")


class PolygonToPintiaApp:
    """主应用程序"""
    
    def __init__(self):
        # 创建主窗口
        if HAS_DND:
            self.root = TkinterDnD.Tk()
        else:
            self.root = tk.Tk()
        
        self.root.title("Polygon → Pintia 测试数据转换工具")
        self.root.geometry("700x750")
        self.root.minsize(550, 550)
        self.root.resizable(True, True)
        
        # 应用目录和临时目录（兼容 PyInstaller 打包后的路径）
        if getattr(sys, 'frozen', False):
            # PyInstaller 打包后，使用 exe 所在目录
            self.app_dir = os.path.realpath(os.path.dirname(sys.executable))
        else:
            self.app_dir = os.path.realpath(os.path.dirname(os.path.abspath(__file__)))
        self.temp_dir = os.path.join(self.app_dir, "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        
        # 当前处理结果
        self.current_result = None
        self.is_processing = False
        
        # 已下载的文件集合（存储 realpath，用于退出清理判断）
        self.downloaded_files: set[str] = set()
        
        # 注册退出清理（atexit 作为兜底，窗口关闭时也会调用）
        atexit.register(self._cleanup_on_exit)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        self._setup_styles()
        self._setup_ui()
        
        # 如果没有 DND 支持，显示提示
        if not HAS_DND:
            self.status_var.set("提示：安装 tkinterdnd2 可启用拖拽功能 (pip install tkinterdnd2)")
    
    def _setup_styles(self):
        """配置 ttk 样式"""
        style = ttk.Style()
        
        # 尝试使用现代主题
        available_themes = style.theme_names()
        if 'vista' in available_themes:
            style.theme_use('vista')
        elif 'winnative' in available_themes:
            style.theme_use('winnative')
        
        # 自定义强调按钮样式
        style.configure(
            "Accent.TButton",
            font=("Segoe UI", 10, "bold"),
        )
    
    def _setup_ui(self):
        """构建 UI"""
        # 主容器
        main_frame = ttk.Frame(self.root, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(
            main_frame,
            text="Polygon → Pintia 测试数据转换工具",
            font=("Segoe UI", 14, "bold"),
        )
        title_label.pack(pady=(0, 5))
        
        subtitle_label = ttk.Label(
            main_frame,
            text="将 Polygon Full 包的测试数据转换为 Pintia (PTA) 兼容格式",
            font=("Segoe UI", 9),
            foreground="#6C757D",
        )
        subtitle_label.pack(pady=(0, 15))
        
        # 拖拽区域
        self.drop_zone = DropZone(main_frame, self)
        self.drop_zone.pack(fill=tk.X, pady=(0, 10))
        
        # 文件选择按钮
        self.select_btn = ttk.Button(
            main_frame,
            text="📂 选择 Polygon Full 包 (.zip)",
            command=self.select_file,
        )
        self.select_btn.pack(pady=(0, 10))
        
        # 进度条
        self.progress_frame = ttk.Frame(main_frame)
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            self.progress_frame,
            variable=self.progress_var,
            mode='determinate',
        )
        self.progress_label = ttk.Label(
            self.progress_frame,
            text="",
            font=("Segoe UI", 9),
            foreground="#6C757D",
        )
        
        # 结果区域
        self.result_frame = ResultFrame(main_frame, self)
        
        # 状态栏
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, padding=(10, 5))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar(value="就绪")
        status_label = ttk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 9),
        )
        status_label.pack(side=tk.LEFT)
    
    def select_file(self):
        """打开文件选择对话框"""
        if self.is_processing:
            messagebox.showinfo("处理中", "请等待当前任务完成后再选择新文件。")
            return
        
        filepath = filedialog.askopenfilename(
            title="选择 Polygon Full 压缩包",
            filetypes=[
                ("ZIP 压缩包", "*.zip"),
                ("所有文件", "*.*"),
            ],
        )
        
        if filepath:
            self.process_file(filepath)
    
    def process_file(self, filepath: str):
        """处理选定的文件"""
        if self.is_processing:
            return
        
        # 验证文件
        if not os.path.isfile(filepath):
            messagebox.showerror("错误", f"文件不存在:\n{filepath}")
            return
        
        if not filepath.lower().endswith('.zip'):
            # 允许非 zip 文件但给出提示
            if not messagebox.askyesno("确认", f"选择的文件不是 .zip 格式:\n{os.path.basename(filepath)}\n\n是否继续处理？"):
                return
        
        # 清理上一次处理留下的临时文件（如果未被下载）
        self._cleanup_current_result()
        
        # 开始处理
        self.is_processing = True
        self.select_btn.config(state=tk.DISABLED)
        self.result_frame.hide_result()
        
        # 显示进度
        self.progress_var.set(0)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        self.progress_label.pack()
        self.progress_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_var.set(f"正在处理: {os.path.basename(filepath)}...")
        
        # 在后台线程中处理
        thread = threading.Thread(
            target=self._process_in_thread,
            args=(filepath,),
            daemon=True,
        )
        thread.start()
    
    def _process_in_thread(self, filepath: str):
        """后台线程处理文件"""
        def progress_callback(current, total, message):
            """线程安全的进度更新"""
            if total > 0:
                progress = (current / total) * 100
            else:
                progress = 0
            self.root.after(0, self._update_progress, progress, message)
        
        result = process_polygon_zip(filepath, self.temp_dir, progress_callback)
        
        # 回到主线程更新 UI
        self.root.after(0, self._on_process_complete, result)
    
    def _update_progress(self, value: float, message: str):
        """更新进度条"""
        self.progress_var.set(value)
        self.progress_label.config(text=message)
    
    def _on_process_complete(self, result: dict):
        """处理完成后的 UI 更新"""
        self.is_processing = False
        self.select_btn.config(state=tk.NORMAL)
        
        # 隐藏进度条
        self.progress_frame.pack_forget()
        self.progress_bar.pack_forget()
        self.progress_label.pack_forget()
        
        if result['success']:
            self.current_result = result
            self.result_frame.show_result(result)
            n_outputs = len(result.get('outputs', []))
            if n_outputs > 1:
                self.status_var.set(f"✅ 处理完成: {n_outputs} 个分卷压缩包")
            else:
                self.status_var.set(f"✅ 处理完成: {result['output_name']}")
        else:
            self.current_result = None
            self.result_frame.hide_result()
            
            # 显示错误
            error_msg = result.get('error', '未知错误')
            messagebox.showerror("处理失败", error_msg)
            self.status_var.set("❌ 处理失败")
    
    def download_generated_file(self, filepath: str, filename: str, ext: str = ".zip"):
        """下载指定的生成文件（复制到用户选择的位置，保留临时文件）"""
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("错误", "临时文件不存在，可能已被删除。")
            return
        
        # 弹出另存为对话框
        save_path = filedialog.asksaveasfilename(
            title=f"保存 {filename}",
            initialfile=filename,
            defaultextension=ext,
            filetypes=[
                (f"{ext} 文件", f"*{ext}"),
                ("所有文件", "*.*"),
            ],
        )
        
        if save_path:
            try:
                shutil.copy2(filepath, save_path)
                self.downloaded_files.add(os.path.realpath(filepath))
                messagebox.showinfo("成功", f"文件已保存到:\n{save_path}")
                self.status_var.set(f"✅ 已下载: {os.path.basename(save_path)}")
            except Exception as e:
                messagebox.showerror("保存失败", f"无法保存文件:\n{str(e)}")
    
    def delete_generated_file(self, filepath: str, label: str = ""):
        """删除指定的生成文件"""
        if not filepath:
            return
        
        if not messagebox.askyesno("确认删除", f"确定要删除 {label} 吗？\n此操作不可撤销。"):
            return
        
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                messagebox.showerror("删除失败", f"无法删除文件:\n{str(e)}")
                return
        
        self.status_var.set(f"🗑 已删除: {label}")
    
    def _cleanup_current_result(self):
        """清理当前结果的所有临时文件（仅删除未被下载的文件；已下载的保留）"""
        if not self.current_result:
            return
        
        # 收集所有需要检查的路径
        all_paths = []
        
        # 测试 zip 文件（可能多个分卷）
        for out in self.current_result.get('outputs', []):
            p = out.get('path')
            if p:
                all_paths.append(p)
        # 兼容旧格式
        output_path = self.current_result.get('output_path')
        if output_path and output_path not in all_paths:
            all_paths.append(output_path)
        
        # 题面文件
        for stmt in self.current_result.get('statements', []):
            sp = stmt.get('output_path')
            if sp:
                all_paths.append(sp)
        
        # 检查并删除未下载的文件
        for path in all_paths:
            if not path or not os.path.exists(path):
                continue
            try:
                real_path = os.path.realpath(path)
            except OSError:
                real_path = path
            
            is_downloaded = any(
                os.path.realpath(dp) == real_path
                for dp in self.downloaded_files
            )
            
            if not is_downloaded:
                try:
                    os.remove(path)
                except OSError:
                    pass
        
        self.current_result = None
        self.result_frame.hide_result()
    
    def _cleanup_on_exit(self):
        """退出时清理 temp 目录中所有残留的临时文件"""
        if not os.path.exists(self.temp_dir):
            return
        
        files_removed = 0
        for filename in os.listdir(self.temp_dir):
            filepath = os.path.join(self.temp_dir, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                os.remove(filepath)
                files_removed += 1
            except OSError:
                pass
        
        if files_removed > 0:
            print(f"[清理] 已删除 {files_removed} 个临时文件")
    
    def _on_close(self):
        """窗口关闭事件"""
        # 检查 temp 目录中是否有未下载的文件，如有则提示用户
        has_undownloaded = False
        if os.path.exists(self.temp_dir):
            downloaded_real = set()
            for dp in self.downloaded_files:
                try:
                    downloaded_real.add(os.path.realpath(dp))
                except OSError:
                    downloaded_real.add(dp)
            
            for filename in os.listdir(self.temp_dir):
                filepath = os.path.join(self.temp_dir, filename)
                if not os.path.isfile(filepath):
                    continue
                try:
                    real_path = os.path.realpath(filepath)
                except OSError:
                    real_path = filepath
                if real_path not in downloaded_real:
                    has_undownloaded = True
                    break
        
        if has_undownloaded:
            if not messagebox.askyesno(
                "确认退出",
                "temp 目录中还有未下载的转换文件。\n退出后临时文件将被自动清理。\n\n确定要退出吗？"
            ):
                return
        
        self._cleanup_on_exit()
        self.root.destroy()
    
    def run(self):
        """启动应用"""
        self.root.mainloop()


def main():
    """应用入口"""
    app = PolygonToPintiaApp()
    app.run()


if __name__ == "__main__":
    main()
