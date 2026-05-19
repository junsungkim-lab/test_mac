#!/usr/bin/env python3
"""
메이플랜드 매크로 GUI
실행: python gui.py
"""

import tkinter as tk
from tkinter import scrolledtext
import threading
import time
import random
from pynput import keyboard
from pynput.keyboard import Key, Controller

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
    return special.get(key_str.strip().lower(), key_str.strip().lower())


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

            # ── 1. 스킬키 반복 press/release (홀드 효과) ─
            # kb.press() 한 번만으론 게임이 오래 못 인식 →
            # 실제 키보드처럼 짧게 반복 입력해야 홀드로 동작
            hold = random.uniform(cfg["hold_min"], cfg["hold_max"])
            self.log(f"[스킬] {cfg['attack_key'].upper()} 키 {hold:.1f}초 홀드")
            deadline = time.time() + hold
            while time.time() < deadline:
                if not self.running or self._stop.is_set():
                    break
                kb.press(self._attack_key)
                time.sleep(0.05)
                kb.release(self._attack_key)
                time.sleep(0.03)
            else:
                pass
            if not self.running or self._stop.is_set():
                break

            # ── 2. 살짝 이동 후 정확히 제자리 복귀 ────
            go  = Key.left  if self._last_dir == "left" else Key.right
            back = Key.right if self._last_dir == "left" else Key.left
            arrow = "←" if self._last_dir == "left" else "→"
            self._last_dir = "right" if self._last_dir == "left" else "left"

            # 이동 시간 = 복귀 시간 (동일하게) → 제자리 보장
            dur = random.uniform(cfg["move_min"], cfg["move_max"])

            self.log(f"[이동] {arrow} {dur:.2f}초 이동 후 복귀")
            kb.press(go)
            time.sleep(dur)
            kb.release(go)
            time.sleep(0.08)   # 방향키 전환 짧은 틈
            kb.press(back)
            time.sleep(dur)    # 똑같은 시간으로 복귀
            kb.release(back)

            # ── 3. 이동 후 짧은 대기 ───────────────────
            pause = random.uniform(cfg["pause_min"], cfg["pause_max"])
            if pause > 0.05:
                self.log(f"[대기] {pause:.2f}초 후 재시작")
            if not self._sleep(pause):
                break

        self._release()
        self.log("[정지] 매크로 종료됨")


# ── GUI ───────────────────────────────────────────────
BG   = "#1e1e2e"
BOX  = "#313244"
FG   = "#cdd6f4"
GRAY = "#6c7086"
GRN  = "#a6e3a1"
RED  = "#f38ba8"
BLU  = "#89b4fa"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("스터디 타이머 알림")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.engine = MacroEngine(self._log)
        self._build_ui()
        self._start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _label(self, parent, text, size=10, color=FG, bold=False, **kw):
        font = ("맑은 고딕", size, "bold" if bold else "normal")
        return tk.Label(parent, text=text, font=font, fg=color, bg=BG, **kw)

    def _build_ui(self):
        # ── 상태 표시 ─────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 4))
        self._dot = tk.Label(top, text="●", font=("Arial", 20), fg=RED, bg=BG)
        self._dot.pack(side="left")
        self._status = tk.Label(top, text="  정지됨",
                                font=("맑은 고딕", 13, "bold"), fg=FG, bg=BG)
        self._status.pack(side="left")

        self._sep()

        # ── 설명 ─────────────────────────────────────
        info = tk.Frame(self, bg=BG)
        info.pack(fill="x", padx=16, pady=(6, 0))
        self._label(info, "동작 순서: 스킬키 홀드  →  살짝 이동 후 제자리 복귀  →  반복",
                    size=9, color=GRAY).pack(anchor="w")

        self._sep()

        # ── 설정 ─────────────────────────────────────
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="x", padx=16, pady=6)

        def field(title, desc, default, row):
            tk.Label(frm, text=title, font=("맑은 고딕", 10, "bold"),
                     fg=FG, bg=BG, anchor="w").grid(
                row=row*2, column=0, sticky="w", pady=(8,0))
            tk.Label(frm, text=desc, font=("맑은 고딕", 8),
                     fg=GRAY, bg=BG, anchor="w").grid(
                row=row*2+1, column=0, sticky="w")
            var = tk.StringVar(value=default)
            tk.Entry(frm, textvariable=var, width=8,
                     bg=BOX, fg=FG, insertbackground=FG,
                     relief="flat", font=("Consolas", 10)).grid(
                row=row*2, column=1, rowspan=2, padx=(16, 0), sticky="w")
            return var

        self.v_key  = field(
            "공격 스킬 키",
            "스킬에 설정된 키보드 키 (예: z, x, a, v)",
            "z", 0)

        self._sep_light(frm, row=2)

        self.v_hold_min = field(
            "스킬 홀드 시간 — 최소 (초)",
            "이 시간 이상 스킬키를 꾹 누름",
            "4", 3)
        self.v_hold_max = field(
            "스킬 홀드 시간 — 최대 (초)",
            "이 시간 이하로 랜덤하게 눌렀다가 이동  ↑ 크면 덜 자주 이동",
            "9", 4)

        self._sep_light(frm, row=5)

        self.v_move_min = field(
            "이동 거리 — 최소 (초)",
            "짧을수록 조금만 움직임  →  떨어질 위험 낮음",
            "0.1", 6)
        self.v_move_max = field(
            "이동 거리 — 최대 (초)",
            "길수록 많이 움직임  →  0.2 이하 권장 (플랫폼 이탈 방지)",
            "0.2", 7)

        self._sep_light(frm, row=8)

        self.v_pause_min = field(
            "이동 후 대기 — 최소 (초)",
            "이동 끝나고 다시 스킬 홀드 전 쉬는 시간",
            "0.0", 9)
        self.v_pause_max = field(
            "이동 후 대기 — 최대 (초)",
            "0이면 바로 재시작  /  1이면 최대 1초 쉬고 재시작",
            "0.5", 10)

        self._sep()

        # ── 버튼 ─────────────────────────────────────
        btn_frm = tk.Frame(self, bg=BG)
        btn_frm.pack(pady=10)

        self._btn = tk.Button(
            btn_frm, text="▶   시 작   (F8)",
            font=("맑은 고딕", 12, "bold"),
            bg=GRN, fg="#1e1e2e", relief="flat",
            padx=24, pady=10, cursor="hand2",
            command=self._toggle)
        self._btn.pack(side="left", padx=6)

        tk.Button(
            btn_frm, text="✕  종료  (F9)",
            font=("맑은 고딕", 10),
            bg=RED, fg="#1e1e2e", relief="flat",
            padx=16, pady=10, cursor="hand2",
            command=self._on_close).pack(side="left", padx=6)

        self._sep()

        # ── 로그 ─────────────────────────────────────
        self._log_box = scrolledtext.ScrolledText(
            self, height=9, width=52,
            bg=BOX, fg=FG, font=("Consolas", 9),
            relief="flat", state="disabled")
        self._log_box.pack(padx=14, pady=(0, 12))

    def _sep(self):
        tk.Frame(self, bg="#45475a", height=1).pack(fill="x", padx=10, pady=4)

    def _sep_light(self, parent, row):
        tk.Frame(parent, bg="#45475a", height=1).grid(
            row=row*2, column=0, columnspan=2, sticky="ew", pady=4)

    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        def _w():
            self._log_box.config(state="normal")
            self._log_box.insert("end", f"[{ts}] {msg}\n")
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, _w)

    def _toggle(self):
        if self.engine.running:
            self.engine.stop()
            self._dot.config(fg=RED)
            self._status.config(text="  정지됨")
            self._btn.config(text="▶   시 작   (F8)", bg=GRN)
        else:
            cfg = self._read_cfg()
            if cfg is None:
                return
            self.engine.start(cfg)
            self._dot.config(fg=GRN)
            self._status.config(text="  실행 중")
            self._btn.config(text="■   정 지   (F8)", bg=RED)
            self._log(f"[시작] 키:{cfg['attack_key'].upper()} "
                      f"홀드:{cfg['hold_min']}~{cfg['hold_max']}s "
                      f"이동:{cfg['move_min']}~{cfg['move_max']}s")

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

    def _start_hotkey_listener(self):
        f8 = _parse_key("f8")
        f9 = _parse_key("f9")
        def on_press(key):
            if key == f8:
                self.after(0, self._toggle)
            elif key == f9:
                self.after(0, self._on_close)
        threading.Thread(
            target=lambda: keyboard.Listener(on_press=on_press).run(),
            daemon=True).start()

    def _on_close(self):
        self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
