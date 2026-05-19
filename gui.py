#!/usr/bin/env python3
"""
메이플랜드 매크로 GUI
실행: python gui.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import random
import sys
from pynput import keyboard
from pynput.keyboard import Key, Controller

# ── 키 파싱 ───────────────────────────────────────────
kb = Controller()

def _parse_key(key_str):
    special = {
        "space": Key.space, "enter": Key.enter, "tab": Key.tab,
        "left": Key.left, "right": Key.right, "up": Key.up, "down": Key.down,
        "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt,
        "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4,
        "f5": Key.f5, "f6": Key.f6, "f7": Key.f7, "f8": Key.f8,
        "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12,
        "home": Key.home, "end": Key.end, "page_up": Key.page_up,
        "page_down": Key.page_down, "delete": Key.delete,
    }
    k = key_str.strip().lower()
    return special.get(k, k)


# ── 매크로 엔진 ───────────────────────────────────────
class MacroEngine:
    def __init__(self, log_fn):
        self.log = log_fn
        self.running = False
        self._thread = None
        self._stop = threading.Event()
        self._last_dir = "left"
        self._attack_key = None

    def start(self, cfg):
        if self.running:
            return
        self._cfg = cfg
        self._attack_key = _parse_key(cfg["attack_key"])
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._release()
        self._stop.set()

    def _release(self):
        try:
            kb.release(self._attack_key)
        except Exception:
            pass

    def _sleep(self, seconds):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if not self.running or self._stop.is_set():
                return False
            time.sleep(0.05)
        return True

    def _loop(self):
        cfg = self._cfg
        while self.running and not self._stop.is_set():
            # Phase 1: 홀드
            hold = random.uniform(cfg["hold_min"], cfg["hold_max"])
            self.log(f"[홀드] {cfg['attack_key'].upper()} 키 {hold:.1f}초 홀드")
            kb.press(self._attack_key)
            if not self._sleep(hold):
                break
            kb.release(self._attack_key)

            # Phase 2: 이동
            move_key   = Key.left  if self._last_dir == "left"  else Key.right
            return_key = Key.right if self._last_dir == "left"  else Key.left
            label = "← 좌이동" if self._last_dir == "left" else "→ 우이동"
            self._last_dir = "right" if self._last_dir == "left" else "left"

            move_dur   = random.uniform(cfg["move_min"], cfg["move_max"])
            return_dur = random.uniform(cfg["move_min"], cfg["move_max"])

            self.log(f"[이동] {label} ({move_dur:.2f}초 → 복귀 {return_dur:.2f}초)")
            kb.press(move_key)
            time.sleep(move_dur)
            kb.release(move_key)
            time.sleep(random.uniform(0.05, 0.15))
            kb.press(return_key)
            time.sleep(return_dur)
            kb.release(return_key)

            # Phase 3: 잠깐 쉬기
            pause = random.uniform(cfg["pause_min"], cfg["pause_max"])
            if pause > 0.05:
                self.log(f"[대기] {pause:.2f}초")
            if not self._sleep(pause):
                break

        self._release()
        self.log("[정지] 매크로 종료")


# ── GUI ───────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("메이플랜드 매크로")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        self.engine = MacroEngine(self._log)
        self._build_ui()
        self._start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI 구성 ──────────────────────────────────────
    def _build_ui(self):
        PAD = dict(padx=12, pady=6)
        BG  = "#1e1e2e"
        FG  = "#cdd6f4"
        BOX = "#313244"
        ACC = "#89b4fa"

        # 상태 표시
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", **PAD)

        self._status_dot = tk.Label(top, text="●", font=("Arial", 22),
                                    fg="#f38ba8", bg=BG)
        self._status_dot.pack(side="left")
        self._status_lbl = tk.Label(top, text=" 정지됨",
                                    font=("Arial", 14, "bold"), fg=FG, bg=BG)
        self._status_lbl.pack(side="left")

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=8, pady=4)

        # 설정 프레임
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="x", **PAD)

        def row(label, default, r):
            tk.Label(frm, text=label, fg=FG, bg=BG, anchor="w",
                     width=18).grid(row=r, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=default)
            tk.Entry(frm, textvariable=var, width=10,
                     bg=BOX, fg=FG, insertbackground=FG,
                     relief="flat").grid(row=r, column=1, sticky="w", padx=8)
            return var

        self.v_key      = row("공격 키",          "z",    0)
        self.v_hold_min = row("홀드 최소 (초)",    "4.0",  1)
        self.v_hold_max = row("홀드 최대 (초)",    "9.0",  2)
        self.v_move_min = row("이동 최소 (초)",    "0.2",  3)
        self.v_move_max = row("이동 최대 (초)",    "0.7",  4)
        self.v_pause_min= row("재홀드 전 대기 최소","0.0",  5)
        self.v_pause_max= row("재홀드 전 대기 최대","1.0",  6)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=8, pady=4)

        # 버튼
        btn_frm = tk.Frame(self, bg=BG)
        btn_frm.pack(**PAD)

        self._btn = tk.Button(btn_frm, text="▶  시작  (F8)",
                              font=("Arial", 13, "bold"),
                              bg="#a6e3a1", fg="#1e1e2e", relief="flat",
                              padx=20, pady=8, cursor="hand2",
                              command=self._toggle)
        self._btn.pack(side="left", padx=4)

        tk.Button(btn_frm, text="✕  종료",
                  font=("Arial", 11), bg="#f38ba8", fg="#1e1e2e",
                  relief="flat", padx=14, pady=8, cursor="hand2",
                  command=self._on_close).pack(side="left", padx=4)

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=8, pady=4)

        # 로그
        self._log_box = scrolledtext.ScrolledText(
            self, height=10, width=50,
            bg=BOX, fg=FG, font=("Consolas", 9),
            relief="flat", state="disabled"
        )
        self._log_box.pack(padx=12, pady=(0, 10))

        tk.Label(self, text="F8: 토글  |  F9: 종료",
                 fg="#6c7086", bg=BG, font=("Arial", 9)).pack(pady=(0, 8))

    # ── 로그 ─────────────────────────────────────────
    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        def _write():
            self._log_box.config(state="normal")
            self._log_box.insert("end", f"[{ts}] {msg}\n")
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, _write)

    # ── 토글 ─────────────────────────────────────────
    def _toggle(self):
        if self.engine.running:
            self.engine.stop()
            self._set_status(False)
        else:
            cfg = self._read_cfg()
            if cfg is None:
                return
            self.engine.start(cfg)
            self._set_status(True)
            self._log(f"[시작] 공격키: {cfg['attack_key'].upper()} "
                      f"홀드 {cfg['hold_min']}~{cfg['hold_max']}초")

    def _set_status(self, active):
        if active:
            self._status_dot.config(fg="#a6e3a1")
            self._status_lbl.config(text=" 실행 중")
            self._btn.config(text="■  정지  (F8)", bg="#f38ba8")
        else:
            self._status_dot.config(fg="#f38ba8")
            self._status_lbl.config(text=" 정지됨")
            self._btn.config(text="▶  시작  (F8)", bg="#a6e3a1")

    def _read_cfg(self):
        try:
            return {
                "attack_key": self.v_key.get().strip() or "z",
                "hold_min":   float(self.v_hold_min.get()),
                "hold_max":   float(self.v_hold_max.get()),
                "move_min":   float(self.v_move_min.get()),
                "move_max":   float(self.v_move_max.get()),
                "pause_min":  float(self.v_pause_min.get()),
                "pause_max":  float(self.v_pause_max.get()),
            }
        except ValueError:
            self._log("[오류] 숫자를 올바르게 입력하세요.")
            return None

    # ── 전역 단축키 (F8/F9) ──────────────────────────
    def _start_hotkey_listener(self):
        f8  = _parse_key("f8")
        f9  = _parse_key("f9")

        def on_press(key):
            if key == f8:
                self.after(0, self._toggle)
            elif key == f9:
                self.after(0, self._on_close)

        t = threading.Thread(
            target=lambda: keyboard.Listener(on_press=on_press).run(),
            daemon=True
        )
        t.start()

    def _on_close(self):
        self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
