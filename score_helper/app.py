# -*- coding: utf-8 -*-
"""
CS2 周经验值计算器 · 桌面版
一个窗口里跑全部：计算器界面（网页）+ 屏幕识别（全局热键 + OCR + 本地服务）
"""
import os
import sys
import threading


def _base_dir():
    # PyInstaller 打包后资源在 sys._MEIPASS，开发时就在脚本目录
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def _find_html():
    cands = []
    if getattr(sys, "frozen", False):
        cands.append(os.path.join(os.path.dirname(sys.executable), "weekly-xp-calculator.html"))
    cands.append(os.path.join(_base_dir(), "weekly-xp-calculator.html"))
    cands.append(os.path.join(os.path.dirname(_base_dir()), "weekly-xp-calculator.html"))
    for p in cands:
        if os.path.exists(p):
            return p
    return None


def _load_html_path():
    """优先用 exe 旁边的网页（改网页不用重新打包）。
    复制一份到临时目录再加载，避开 WebView2 的页面缓存。"""
    src = _find_html()
    if not src:
        return None
    try:
        import shutil
        import tempfile
        tmpdir = os.path.join(tempfile.gettempdir(), "cs2xp_ui")
        if not os.path.isdir(tmpdir):
            os.makedirs(tmpdir, exist_ok=True)
        dst = os.path.join(tmpdir, "weekly-xp-calculator.html")
        same = False
        if os.path.exists(dst):
            try:
                same = abs(os.path.getmtime(dst) - os.path.getmtime(src)) < 1
            except Exception:
                same = False
        if not same:
            shutil.copyfile(src, dst)
            os.utime(dst, (os.path.getatime(src), os.path.getmtime(src)))
        return "file:///" + dst.replace("\\", "/")
    except Exception:
        return "file:///" + src.replace("\\", "/")


class Api:
    """网页直连 Python（不走 HTTP，浏览器有代理也能用）"""

    def get_state(self):
        try:
            import score_helper as sh
            with sh._lock:
                return dict(sh._state)
        except Exception:
            return {"score": None, "status": "助手未就绪"}

    def push_config(self, cfg):
        try:
            import score_helper as sh
            c = sh.load_cfg()
            for k in ("name", "hotkey", "auto", "region"):
                if k in cfg:
                    c[k] = cfg[k]
            sh.save_cfg(c)
            sh.rebind_hotkey()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def start_capture(self):
        import threading
        try:
            import score_helper as sh
            threading.Thread(target=sh.start_capture, daemon=True).start()
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def main():
    # 1) 后台服务：本地 HTTP(8787) + 全局热键 + OCR（和小助手同一套代码）
    try:
        import score_helper as sh
        sh.serve()
        sh.rebind_hotkey()
    except Exception as e:
        print("识别模块启动失败（计算器仍可用）：%s" % e, file=sys.stderr)

    # 2) 窗口
    import webview

    url = _load_html_path()
    if not url:
        import tkinter.messagebox as mb
        mb.showerror("错误", "找不到 weekly-xp-calculator.html")
        return

    win = webview.create_window(
        "CS2 周经验值加成 / 衰减机制 计算器",
        url,
        width=1180,
        height=860,
        min_size=(960, 620),
        text_select=False,
        js_api=Api(),
    )
    # 关窗口时退出进程（热键线程还在后台）
    win.events.closed += lambda: os._exit(0)
    webview.start()


if __name__ == "__main__":
    main()
