"""
Polygon → Pintia 测试数据转换工具
===================================

将 Polygon (codeforces.com) Full 包中的测试数据转换为
Pintia (PTA) 兼容格式。

用法:
    python main.py          # 启动 GUI 应用
    python main.py --help   # 查看帮助
"""

import sys
import os

# 确保脚本目录在路径中（兼容 PyInstaller 打包）
if getattr(sys, 'frozen', False):
    script_dir = os.path.dirname(sys.executable)
else:
    script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)


def check_dependencies():
    """检查必要的依赖"""
    missing = []
    
    try:
        import tkinter
    except ImportError:
        missing.append("tkinter (Python 标准库，请确保已安装)")
    
    try:
        from tkinterdnd2 import TkinterDnD
    except ImportError:
        # tkinterdnd2 是可选的，仅用于拖拽功能
        print("[提示] 未安装 tkinterdnd2，拖拽功能不可用。")
        print("       可通过文件选择按钮来加载压缩包。")
        print("       如需拖拽功能，请执行: pip install tkinterdnd2")
        print()
    
    if missing:
        print("缺少必要依赖:")
        for m in missing:
            print(f"  - {m}")
        print("\n请安装后再运行。")
        sys.exit(1)


def main():
    """主入口"""
    print("=" * 60)
    print("  Polygon → Pintia 测试数据转换工具")
    print("=" * 60)
    print()
    
    check_dependencies()
    
    try:
        from app import PolygonToPintiaApp
        app = PolygonToPintiaApp()
        app.run()
    except Exception as e:
        print(f"\n[错误] 应用启动失败: {e}")
        import traceback
        traceback.print_exc()
        
        # 如果是 GUI 环境，尝试显示错误对话框
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "启动失败",
                f"应用启动失败:\n\n{type(e).__name__}: {str(e)}\n\n"
                f"请检查依赖是否安装完整。"
            )
            root.destroy()
        except Exception:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
