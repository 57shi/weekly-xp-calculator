# -*- coding: utf-8 -*-
"""
CS2 计算器 · 截图小助手（微信风格）
按热键 -> 屏幕冻结变暗 -> 拖框选区域 -> 松手出工具栏（复制 / 保存 / 取消）
快捷键、是否自动复制 都可在小窗口里改，也会同步到网页参数设置
"""
import io
import json
import os
import sys
import threading
import time
from datetime import datetime

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

CFG = os.path.join(BASE, "score_config.json")
STATE = os.path.join(BASE, "score_state.json")
SHOTS = os.path.join(BASE, "截图")
DEFAULT_CFG = {"name": "", "hotkey": "o", "auto": True, "region": None}

_lock = threading.Lock()
_state = {"score": None, "name": "", "status": "就绪", "time": 0.0, "auto": True,
          "shot": ""}
_ROOT = None


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CFG, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        with open(CFG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def set_state(**kw):
    with _lock:
        _state.update(kw)
        _state["time"] = time.time()
        try:
            with open(STATE, "w", encoding="utf-8") as f:
                json.dump(_state, f, ensure_ascii=False)
        except Exception:
            pass


def status_text(t):
    set_state(status=t)


# ---------------- 抓屏 ----------------
def grab_full():
    import mss
    import numpy as np
    from PIL import Image
    with mss.mss() as sct:
        mon = sct.monitors[1]
        shot = sct.grab(mon)
        return Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)


# ---------------- 剪贴板 ----------------
def copy_to_clipboard(img):
    import win32clipboard
    import win32con
    output = io.BytesIO()
    img.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_DIB, data)
    finally:
        win32clipboard.CloseClipboard()


def save_shot(img):
    if not os.path.isdir(SHOTS):
        os.makedirs(SHOTS, exist_ok=True)
    name = "截图_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".png"
    path = os.path.join(SHOTS, name)
    img.save(path)
    return path


# ---------------- 认数字 ----------------
_ocr = None


def engine():
    global _ocr
    if _ocr is None:
        status_text("正在加载识别引擎（首次约十几秒）…")
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    return _ocr


def ocr_number(img):
    """PIL Image -> 整数或 None（只认 0-9）"""
    import re as _re
    dets, _ = engine()(img)
    if not dets:
        return None
    nums = []
    for _box, text, _conf in dets:
        m = _re.fullmatch(r"\s*(\d{1,4})\s*", str(text or ""))
        if m:
            nums.append((int(m.group(1)), str(text)))
    if not nums:
        return None
    nums.sort(key=lambda t: -len(t[1]))
    return nums[0][0]


# ---------------- 截图主流程 ----------------
import queue as _queue

_TK_Q = _queue.Queue()
_TK_STARTED = {"v": False}


def _tk_loop():
    """独立线程里跑一个隐藏的 tk 根（exe 模式下没有助手窗口，用它来显示框选层）"""
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    global _ROOT
    _ROOT = root

    def pump():
        try:
            while True:
                fn = _TK_Q.get_nowait()
                if fn is None:
                    root.destroy()
                    return
                try:
                    fn()
                except Exception as e:
                    status_text("出错：%s" % e)
        except _queue.Empty:
            pass
        root.after(80, pump)

    root.after(80, pump)
    root.mainloop()


def ensure_tk():
    if _ROOT is not None or _TK_STARTED["v"]:
        return
    _TK_STARTED["v"] = True
    threading.Thread(target=_tk_loop, daemon=True).start()
    for _ in range(60):                     # 等它就绪
        if _ROOT is not None:
            return
        time.sleep(0.05)


def start_capture():
    """按热键：冻结屏幕并进入框选"""
    status_text("抓屏中…")
    try:
        img = grab_full()
    except Exception as e:
        status_text("抓屏失败：%s" % e)
        return
    ensure_tk()
    if _ROOT is None:
        status_text("界面还没起来，稍等一下再按")
        return
    _TK_Q.put(lambda: _show_overlay(img))


def _show_overlay(img_full):
    import tkinter as tk
    from PIL import ImageTk

    sw = _ROOT.winfo_screenwidth()
    sh = _ROOT.winfo_screenheight()
    if img_full.size != (sw, sh):
        img_full = img_full.resize((sw, sh))

    top = tk.Toplevel(_ROOT)
    top.attributes("-fullscreen", True, "-topmost", True)
    top.configure(bg="black")
    top.focus_force()

    cv = tk.Canvas(top, bg="black", cursor="cross", highlightthickness=0)
    cv.pack(fill="both", expand=True)
    tk_img = ImageTk.PhotoImage(img_full)
    cv.create_image(0, 0, anchor="nw", image=tk_img)
    cv._tkimg = tk_img

    dim_id = {"r": None}
    DIM = "#1b1f24"
    sel = {"x": 0, "y": 0, "r": None}
    tip = cv.create_text(0, 0, text="", fill="#ffd60a",
                         font=("Microsoft YaHei", 12, "bold"))
    hint = tk.Label(top, text="拖框选区域 · 松手出工具栏 · Esc 取消 · 双击直接复制",
                    bg="#111721", fg="#ffd60a", font=("Microsoft YaHei", 12, "bold"),
                    padx=12, pady=5)
    hint.place(relx=0.5, y=24, anchor="center")

    def redraw_dim(x0, y0, x1, y1):
        # 选区外压暗（微信那种效果：里面亮、外面暗）
        if dim_id["r"]:
            for r in dim_id["r"]:
                cv.delete(r)
        dim_id["r"] = [
            cv.create_rectangle(0, 0, sw, y0, fill=DIM, stipple="gray50", outline=""),
            cv.create_rectangle(0, y1, sw, sh, fill=DIM, stipple="gray50", outline=""),
            cv.create_rectangle(0, y0, x0, y1, fill=DIM, stipple="gray50", outline=""),
            cv.create_rectangle(x1, y0, sw, y1, fill=DIM, stipple="gray50", outline=""),
        ]
        cv.tag_lower(dim_id["r"][0]); cv.tag_lower(dim_id["r"][1])
        cv.tag_lower(dim_id["r"][2]); cv.tag_lower(dim_id["r"][3])

    def down(e):
        sel["x"], sel["y"] = e.x, e.y
        if sel["r"]:
            cv.delete(sel["r"])
        sel["r"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline="#ffd60a", width=1)
        cv.itemconfig(tip, text="")

    def move(e):
        x0, y0 = sel["x"], sel["y"]
        x1, y1 = e.x, e.y
        if sel["r"]:
            cv.coords(sel["r"], x0, y0, x1, y1)
        redraw_dim(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        cv.coords(tip, (x0 + x1) / 2 + 6, y0 - 12)
        cv.itemconfig(tip, text="%d × %d" % (abs(x1 - x0), abs(y1 - y0)))

    def finish(x1, y1):
        x0, y0 = sel["x"], sel["y"]
        rx0, ry0 = min(x0, x1), min(y0, y1)
        rx1, ry1 = max(x0, x1), max(y0, y1)
        if rx1 - rx0 < 6 or ry1 - ry0 < 6:
            cancel()
            return
        crop = img_full.crop((rx0, ry0, rx1, ry1))
        top.destroy()
        _show_toolbar(crop)

    def cancel():
        status_text("已取消截图")
        top.destroy()

    def dbl(e):
        x0, y0 = sel["x"], sel["y"]
        x1, y1 = e.x, e.y
        rx0, ry0 = min(x0, x1), min(y0, y1)
        rx1, ry1 = max(x0, x1), max(y0, y1)
        if rx1 - rx0 < 6 or ry1 - ry0 < 6:
            return
        crop = img_full.crop((rx0, ry0, rx1, ry1))
        top.destroy()
        _quick_copy(crop)

    cv.bind("<ButtonPress-1>", down)
    cv.bind("<B1-Motion>", move)
    cv.bind("<ButtonRelease-1>", lambda e: finish(e.x, e.y))
    cv.bind("<Double-Button-1>", dbl)
    top.bind("<Escape>", lambda e: cancel())


def _quick_copy(crop):
    try:
        copy_to_clipboard(crop)
        status_text("已复制到剪贴板（%d × %d）" % (crop.width, crop.height))
    except Exception as e:
        status_text("复制失败：%s" % e)


def _ocr_fill(crop):
    """识别框里的数字 -> 发给网页（网页自动填入并点确定）"""
    status_text("识别中…")
    try:
        big = crop.resize((crop.width * 4, crop.height * 4))
        num = ocr_number(big)
    except Exception as e:
        status_text("识别失败：%s" % e)
        return
    if num is None:
        status_text("没认出数字，重截一次（框只框数字）")
        return
    set_state(score=num, status="识别到 %d 分" % num)


def _show_toolbar(crop):
    """松手后的小工具栏：复制 / 保存 / 取消"""
    import tkinter as tk
    from PIL import ImageTk

    bar = tk.Toplevel(_ROOT)
    bar.attributes("-topmost", True)
    bar.overrideredirect(True)
    bar.configure(bg="#111721", highlightthickness=1, highlightbackground="#3a4756")
    F = ("Microsoft YaHei", 10)

    tk.Label(bar, text="%d × %d" % (crop.width, crop.height), bg="#111721", fg="#8b98a5",
             font=("Microsoft YaHei", 9)).pack(side="left", padx=(10, 8))

    def act_ocr():
        bar.destroy()
        threading.Thread(target=_ocr_fill, args=(crop,), daemon=True).start()

    def act_shot():
        # 截图 = 存文件 + 复制到剪贴板
        try:
            p = save_shot(crop)
            copy_to_clipboard(crop)
            status_text("已截图并复制：" + p)
        except Exception as e:
            status_text("截图失败：%s" % e)
        bar.destroy()

    def act_cancel():
        status_text("已取消")
        bar.destroy()

    for txt, cmd, col in (("提取文字", act_ocr, "#1f6f43"),
                          ("截图", act_shot, "#1e2733"),
                          ("取消", act_cancel, "#2a1f22")):
        tk.Button(bar, text=txt, font=F, bg=col, fg="#fff", relief="flat",
                  cursor="hand2", padx=14, pady=6, command=cmd).pack(side="left", padx=3, pady=4)

    # 出现在选区下方中间
    bar.update_idletasks()
    w = bar.winfo_reqwidth()
    h = bar.winfo_reqheight()
    x = _ROOT.winfo_pointerx() - w // 2
    y = _ROOT.winfo_pointery() + 18
    x = max(0, min(x, _ROOT.winfo_screenwidth() - w))
    y = max(0, min(y, _ROOT.winfo_screenheight() - h))
    bar.geometry("+%d+%d" % (x, y))
    bar.bind("<Escape>", lambda e: act_cancel())


# ---------------- 本地 HTTP（只用来同步设置/状态） ----------------
def serve():
    import http.server
    import socketserver

    class H(http.server.BaseHTTPRequestHandler):
        def _json(self, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/score":
                with _lock:
                    self._json(dict(_state))
            elif path == "/config":
                self._json(load_cfg())
            elif path == "/shot":
                threading.Thread(target=start_capture, daemon=True).start()
                self._json({"ok": True})
            else:
                self.send_error(404)

        def do_POST(self):
            path = self.path.split("?")[0]
            if path == "/config":
                n = int(self.headers.get("Content-Length", 0) or 0)
                raw = self.rfile.read(n).decode("utf-8") if n else "{}"
                try:
                    new = json.loads(raw)
                    cfg = load_cfg()
                    for k in ("name", "hotkey", "auto", "region"):
                        if k in new:
                            cfg[k] = new[k]
                    # 热键做个基本校验，别被脏数据搞坏
                    hot = str(cfg.get("hotkey") or "o").strip().lower()
                    if (not hot) or len(hot) > 12 or ("\\" in hot):
                        hot = "o"
                    cfg["hotkey"] = hot
                    save_cfg(cfg)
                    rebind_hotkey()
                    set_state(status="已保存：热键 %s" % str(cfg.get("hotkey") or "o").upper())
                    self._json({"ok": True, "cfg": cfg})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)})
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", 8787), H)
    except Exception as e:
        status_text("8787 端口被占用：%s" % e)
        return
    threading.Thread(target=httpd.serve_forever, daemon=True).start()


# ---------------- 全局热键 ----------------
_hk = {"h": None}


def rebind_hotkey():
    import keyboard
    cfg = load_cfg()
    if _hk["h"] is not None:
        try:
            keyboard.remove_hotkey(_hk["h"])
        except Exception:
            pass
        _hk["h"] = None
    key = (cfg.get("hotkey") or "o").lower()
    try:
        _hk["h"] = keyboard.add_hotkey(key, start_capture, suppress=False)
        status_text("就绪：按 %s 开始截图（拖框选区域）" % key.upper())
    except Exception as e:
        status_text("热键注册失败：%s（换个键试试）" % e)


# ---------------- 窗口 ----------------
def ui():
    import tkinter as tk

    global _ROOT
    cfg = load_cfg()
    root = tk.Tk()
    _ROOT = root
    root.title("截图小助手")
    root.attributes("-topmost", True)
    root.geometry("360x250+24+80")
    root.configure(bg="#111721")
    F = ("Microsoft YaHei", 10)

    tk.Label(root, text="截图小助手（微信那样用）", bg="#111721", fg="#ffd60a",
             font=("Microsoft YaHei", 13, "bold")).pack(pady=(14, 6))
    tk.Label(root, text="任意画面停住 → 按 热键 → 拖框选区域 →\n松手出工具栏：提取文字 / 截图。\n「提取文字」识别框里的数字并自动填进网页；「截图」存到旁边的「截图」文件夹并复制到剪贴板。",
             bg="#111721", fg="#9fb0bf", font=F, justify="left", wraplength=320).pack(padx=14)

    row = tk.Frame(root, bg="#111721")
    row.pack(fill="x", padx=14, pady=(12, 0))
    tk.Label(row, text="热键", bg="#111721", fg="#9fb0bf", font=F).pack(side="left")
    hot_e = tk.Entry(row, font=F, bg="#0d1116", fg="#e8eef4", width=6, relief="flat",
                     highlightthickness=1, highlightbackground="#2c3641")
    hot_e.insert(0, str(cfg.get("hotkey") or "o").upper())
    hot_e.pack(side="left", padx=(6, 12))
    auto_v = tk.BooleanVar(value=bool(cfg.get("auto", True)))
    tk.Checkbutton(row, text="双击选区直接复制", variable=auto_v, bg="#111721", fg="#9fb0bf",
                   font=F, selectcolor="#111721", activebackground="#111721",
                   activeforeground="#ffd60a").pack(side="left")

    btns = tk.Frame(root, bg="#111721")
    btns.pack(fill="x", padx=14, pady=10)
    tk.Button(btns, text="保存", font=F, bg="#1e2733", fg="#cfd8e0", relief="flat",
              cursor="hand2", padx=12, command=lambda: on_save()).pack(side="left")
    tk.Button(btns, text="立即截图", font=F, bg="#1f6f43", fg="#fff", relief="flat",
              cursor="hand2", padx=12,
              command=lambda: threading.Thread(target=start_capture, daemon=True).start()).pack(side="left", padx=(8, 0))
    tk.Button(btns, text="打开截图文件夹", font=F, bg="#1e2733", fg="#cfd8e0", relief="flat",
              cursor="hand2", padx=10,
              command=lambda: os.startfile(SHOTS) if os.path.isdir(SHOTS) else None).pack(side="left", padx=(8, 0))

    tk.Label(root, text="状态", bg="#111721", fg="#9fb0bf", font=F, anchor="w").pack(fill="x", padx=14)
    st_v = tk.StringVar(value="就绪")
    tk.Label(root, textvariable=st_v, bg="#0d1116", fg="#6f7d8b",
             font=("Microsoft YaHei", 9), wraplength=320, justify="left").pack(fill="x", padx=14, pady=(2, 10))

    def on_save():
        cfg = load_cfg()
        hot = hot_e.get().strip() or "O"
        cfg["hotkey"] = hot.lower()
        cfg["auto"] = bool(auto_v.get())
        save_cfg(cfg)
        rebind_hotkey()
        st_v.set("已保存，热键 %s" % hot.upper())

    def poll():
        with _lock:
            s = dict(_state)
        st_v.set(s.get("status") or "")
        root.after(300, poll)

    poll()
    root.mainloop()


def main():
    if not os.path.isdir(SHOTS):
        try:
            os.makedirs(SHOTS, exist_ok=True)
        except Exception:
            pass
    serve()
    rebind_hotkey()          # 先注册热键（窗口起来前也能用）
    try:
        ui()
    except Exception:
        try:
            import keyboard
            keyboard.wait()
        except Exception:
            while True:
                time.sleep(3600)


if __name__ == "__main__":
    main()
