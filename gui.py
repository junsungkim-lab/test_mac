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
kb_lock = threading.Lock()

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


# ── 화면에서 캐릭터 X 좌표 찾기 ──────────────────────────
def find_char_screen_x(char_y, char_color, scan_x, scan_w, tolerance=30):
    """
    게임 화면의 특정 Y 높이 주변에서 char_color를 스캔해 X 좌표 반환.
    char_y   : 캐릭터가 있는 화면 Y 좌표
    char_color: (R, G, B) 저장된 캐릭터 색상
    scan_x   : 스캔 시작 X (게임 창 왼쪽 끝)
    scan_w   : 스캔 너비 (게임 창 너비)
    """
    try:
        import pyautogui
        # 캐릭터 Y 기준 ±40px 범위만 스캔 (속도 최적화)
        region = (scan_x, max(0, char_y - 40), scan_w, 80)
        img = pyautogui.screenshot(region=region)
        pixels = img.load()
        w, h = img.size
        cr, cg, cb = char_color
        found = []
        for x in range(w):
            for y in range(h):
                r, g, b = pixels[x, y]
                if (abs(r - cr) < tolerance and
                    abs(g - cg) < tolerance and
                    abs(b - cb) < tolerance):
                    found.append(scan_x + x)
        if found:
            return int(sum(found) / len(found))
        return None
    except Exception:
        return None


# ── 매크로 엔진 ───────────────────────────────────────────
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

            # ── 1. 스킬키 홀드 ────────────────────────────
            hold = random.uniform(cfg["hold_min"], cfg["hold_max"])
            self.log(f"[스킬] {cfg['attack_key'].upper()} {hold:.1f}초 홀드")
            deadline = time.time() + hold
            while time.time() < deadline:
                if not self.running or self._stop.is_set():
                    break
                with kb_lock:
                    kb.press(self._attack_key)
                    time.sleep(0.05)
                    kb.release(self._attack_key)
                time.sleep(0.03)
            if not self.running or self._stop.is_set():
                break

            # ── 2. 후딜레이 대기 ──────────────────────────
            time.sleep(cfg["after_skill_delay"])

            # ── 3. 경계 확인 → 이동 방향 결정 ────────────
            forced_dir = None
            if cfg["boundary_on"] and cfg["char_color"]:
                char_x = find_char_screen_x(
                    cfg["char_y"],
                    cfg["char_color"],
                    cfg["scan_x"],
                    cfg["scan_w"],
                )
                if char_x is not None:
                    self.log(f"[위치] 화면 X={char_x} "
                             f"(한계 {cfg['bd_left']}~{cfg['bd_right']})")
                    if char_x <= cfg["bd_left"]:
                        forced_dir = "right"
                    elif char_x >= cfg["bd_right"]:
                        forced_dir = "left"

            if forced_dir:
                move_dir = forced_dir
                self._last_dir = "left" if forced_dir == "right" else "right"
            else:
                move_dir = self._last_dir
                self._last_dir = "right" if self._last_dir == "left" else "left"

            go   = Key.left  if move_dir == "left" else Key.right
            back = Key.right if move_dir == "left" else Key.left
            arrow = "←" if move_dir == "left" else "→"
            dur  = random.uniform(cfg["move_min"], cfg["move_max"])

            self.log(f"[이동] {arrow} {dur:.2f}초"
                     + (" ← 경계 보정" if forced_dir else ""))
            with kb_lock:
                kb.press(go)
            time.sleep(dur)
            with kb_lock:
                kb.release(go)
            time.sleep(0.08)
            with kb_lock:
                kb.press(back)
            time.sleep(dur)
            with kb_lock:
                kb.release(back)

            # ── 4. 이동 후 대기 ───────────────────────────
            pause = random.uniform(cfg["pause_min"], cfg["pause_max"])
            if pause > 0.05:
                self.log(f"[대기] {pause:.2f}초")
            if not self._sleep(pause):
                break

        self._release()
        self.log("[정지] 매크로 종료됨")


# ── 평타 엔진 ─────────────────────────────────────────────
class NormalAttackEngine:
    def __init__(self, log_fn):
        self.log = log_fn
        self.running = False
        self._thread = None
        self._stop = threading.Event()

    def start(self, cfg):
        if self.running:
            return
        self._cfg = cfg
        self.running = True
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop.set()

    def _sleep(self, seconds):
        deadline = time.time() + seconds
        while time.time() < deadline:
            if not self.running or self._stop.is_set():
                return False
            time.sleep(0.05)
        return True

    def _loop(self):
        cfg = self._cfg
        key      = _parse_key(cfg["normal_key"])
        interval = cfg["normal_interval"]
        count    = cfg["normal_count"]
        if not self._sleep(interval):
            return
        while self.running and not self._stop.is_set():
            self.log(f"[평타] {cfg['normal_key'].upper()} {count}회")
            for _ in range(count):
                if not self.running or self._stop.is_set():
                    break
                with kb_lock:
                    kb.press(key)
                    time.sleep(0.06)
                    kb.release(key)
                time.sleep(random.uniform(0.08, 0.15))
            jitter = interval * random.uniform(-0.1, 0.1)
            if not self._sleep(interval + jitter):
                break
        self.log("[평타] 종료")


# ── GUI ───────────────────────────────────────────────────
BG   = "#1e1e2e"
BOX  = "#313244"
FG   = "#cdd6f4"
GRAY = "#6c7086"
GRN  = "#a6e3a1"
RED  = "#f38ba8"
BLU  = "#89b4fa"
PUR  = "#cba6f7"

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("스터디 타이머 알림")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.engine = MacroEngine(self._log)
        self.natk   = NormalAttackEngine(self._log)
        self._char_color = None   # (R, G, B) 저장된 캐릭터 색상
        self._build_ui()
        self._start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        # ── 상태 ──────────────────────────────────────────
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 4))
        self._dot = tk.Label(top, text="●", font=("Arial", 20), fg=RED, bg=BG)
        self._dot.pack(side="left")
        self._status = tk.Label(top, text="  정지됨",
                                font=("맑은 고딕", 13, "bold"), fg=FG, bg=BG)
        self._status.pack(side="left")
        self._sep()

        tk.Label(self,
                 text="  동작: 스킬 홀드 → 후딜 대기 → 위치확인 → 이동 → 반복",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)
        self._sep()

        # ── 스킬 설정 ──────────────────────────────────────
        frm = tk.Frame(self, bg=BG)
        frm.pack(fill="x", padx=16, pady=6)

        def field(parent, title, desc, default, row):
            tk.Label(parent, text=title, font=("맑은 고딕", 10, "bold"),
                     fg=FG, bg=BG, anchor="w").grid(
                row=row*2, column=0, sticky="w", pady=(8,0))
            tk.Label(parent, text=desc, font=("맑은 고딕", 8),
                     fg=GRAY, bg=BG, anchor="w").grid(
                row=row*2+1, column=0, sticky="w")
            var = tk.StringVar(value=default)
            tk.Entry(parent, textvariable=var, width=8,
                     bg=BOX, fg=FG, insertbackground=FG,
                     relief="flat", font=("Consolas", 10)).grid(
                row=row*2, column=1, rowspan=2, padx=(16,0), sticky="w")
            return var

        self.v_key       = field(frm, "공격 스킬 키", "예: z, x, a, v", "z", 0)
        self._sep_light(frm, 1)
        self.v_hold_min  = field(frm, "홀드 최소 (초)", "이 시간 이상 꾹 누름", "4", 2)
        self.v_hold_max  = field(frm, "홀드 최대 (초)", "이 시간 이하로 눌렀다 이동", "9", 3)
        self._sep_light(frm, 4)
        self.v_move_min  = field(frm, "이동 거리 최소 (초)", "짧을수록 조금 움직임", "0.1", 5)
        self.v_move_max  = field(frm, "이동 거리 최대 (초)", "0.2 이하 권장", "0.2", 6)
        self._sep_light(frm, 7)
        self.v_pause_min = field(frm, "이동 후 대기 최소 (초)", "이동 끝나고 쉬는 시간", "0.0", 8)
        self.v_pause_max = field(frm, "이동 후 대기 최대 (초)", "0이면 바로 재시작", "0.5", 9)
        self._sep_light(frm, 10)
        self.v_after     = field(frm, "스킬 후딜레이 (초)",
                                 "스킬 뗀 후 이동 전 대기 → 제자리 보장", "0.3", 11)

        self._sep()

        # ── 경계 설정 ─────────────────────────────────────
        bd_row = tk.Frame(self, bg=BG)
        bd_row.pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(bd_row, text="  경계 설정",
                 font=("맑은 고딕", 10, "bold"), fg=PUR, bg=BG).pack(side="left")
        self.v_boundary_on = tk.BooleanVar(value=False)
        tk.Checkbutton(bd_row, text="사용", variable=self.v_boundary_on,
                       font=("맑은 고딕", 9), fg=FG, bg=BG,
                       selectcolor=BOX, activebackground=BG).pack(side="left", padx=8)

        tk.Label(self,
                 text="  게임 화면에서 캐릭터 색상을 저장 → 이동 전마다 X 좌표 확인",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        frm_bd = tk.Frame(self, bg=BG)
        frm_bd.pack(fill="x", padx=16, pady=4)

        self.v_char_y  = field(frm_bd, "캐릭터 화면 Y",
                               "캐릭터가 있는 화면의 세로 위치 (픽셀)", "400", 0)
        self.v_scan_x  = field(frm_bd, "게임 창 왼쪽 X",
                               "게임 창 왼쪽 끝 화면 픽셀 (창모드 위치)", "0", 1)
        self.v_scan_w  = field(frm_bd, "게임 창 너비",
                               "게임 창 가로 크기 (픽셀)", "1024", 2)
        self._sep_light(frm_bd, 3)
        self.v_bd_left  = field(frm_bd, "왼쪽 한계 X",
                                "이 X 이하면 강제 오른쪽 이동", "200", 4)
        self.v_bd_right = field(frm_bd, "오른쪽 한계 X",
                                "이 X 이상이면 강제 왼쪽 이동", "800", 5)

        # 색상 선택 + 테스트 버튼
        color_row = tk.Frame(self, bg=BG)
        color_row.pack(pady=6)

        self._color_btn = tk.Button(
            color_row, text="🎯  색상 저장 (3초 후 마우스 위치)",
            font=("맑은 고딕", 9), bg=BOX, fg=FG,
            relief="flat", padx=10, pady=5, cursor="hand2",
            command=self._pick_color)
        self._color_btn.pack(side="left", padx=4)

        tk.Button(
            color_row, text="📍  위치 테스트",
            font=("맑은 고딕", 9), bg=BOX, fg=FG,
            relief="flat", padx=10, pady=5, cursor="hand2",
            command=self._test_pos).pack(side="left", padx=4)

        self._color_preview = tk.Label(
            self, text="  색상 미저장", font=("맑은 고딕", 8),
            fg=GRAY, bg=BG)
        self._color_preview.pack()

        self._sep()

        # ── 평타 섹션 ─────────────────────────────────────
        tk.Label(self, text="  매크로 감지 몬스터 처리 (평타)",
                 font=("맑은 고딕", 10, "bold"), fg=BLU, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(6,0))
        tk.Label(self, text="  스킬과 별개로 주기적으로 평타 키 자동 입력",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        frm2 = tk.Frame(self, bg=BG)
        frm2.pack(fill="x", padx=16, pady=6)
        self.v_natk_key      = field(frm2, "평타 키", "예: ctrl, x, c", "ctrl", 0)
        self.v_natk_interval = field(frm2, "평타 주기 (초)", "몇 초마다 한 번", "60", 1)
        self.v_natk_count    = field(frm2, "평타 횟수", "한 번에 몇 번 연타", "3", 2)

        natk_row = tk.Frame(self, bg=BG)
        natk_row.pack(pady=(4,0))
        self._natk_btn = tk.Button(
            natk_row, text="▶  평타 ON",
            font=("맑은 고딕", 10, "bold"), bg=BLU, fg="#1e1e2e",
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._toggle_natk)
        self._natk_btn.pack()

        self._sep()

        # ── 메인 버튼 ─────────────────────────────────────
        btn_row = tk.Frame(self, bg=BG)
        btn_row.pack(pady=10)
        self._btn = tk.Button(
            btn_row, text="▶   시 작   (F8)",
            font=("맑은 고딕", 12, "bold"), bg=GRN, fg="#1e1e2e",
            relief="flat", padx=24, pady=10, cursor="hand2",
            command=self._toggle)
        self._btn.pack(side="left", padx=6)
        tk.Button(btn_row, text="✕  종료  (F9)",
                  font=("맑은 고딕", 10), bg=RED, fg="#1e1e2e",
                  relief="flat", padx=16, pady=10, cursor="hand2",
                  command=self._on_close).pack(side="left", padx=6)

        self._sep()

        # ── 로그 ──────────────────────────────────────────
        self._log_box = scrolledtext.ScrolledText(
            self, height=9, width=54,
            bg=BOX, fg=FG, font=("Consolas", 9),
            relief="flat", state="disabled")
        self._log_box.pack(padx=14, pady=(0, 12))

    # ── 유틸 ──────────────────────────────────────────────
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

    # ── 색상 선택 ─────────────────────────────────────────
    def _pick_color(self):
        self._color_btn.config(text="⏳  3초 후 저장...", state="disabled")
        self._log("[색상] 3초 후 마우스 위치 색상 저장 — 캐릭터 위에 올려두세요")
        def _run():
            time.sleep(3)
            try:
                import pyautogui
                x, y = pyautogui.position()
                color = pyautogui.pixel(x, y)
                self._char_color = (color[0], color[1], color[2])
                r, g, b = self._char_color
                self.after(0, lambda: self._on_color_saved(r, g, b))
            except Exception as e:
                self._log(f"[오류] 색상 저장 실패: {e}")
                self.after(0, lambda: self._color_btn.config(
                    text="🎯  색상 저장 (3초 후 마우스 위치)", state="normal"))
        threading.Thread(target=_run, daemon=True).start()

    def _on_color_saved(self, r, g, b):
        self._color_btn.config(
            text="🎯  색상 재저장 (3초 후 마우스 위치)", state="normal")
        self._color_preview.config(
            text=f"  저장된 색상: RGB({r}, {g}, {b})", fg=GRN)
        self._log(f"[색상] RGB({r}, {g}, {b}) 저장 완료")

    # ── 위치 테스트 ───────────────────────────────────────
    def _test_pos(self):
        if not self._char_color:
            self._log("[테스트] 먼저 색상을 저장하세요")
            return
        try:
            char_y = int(self.v_char_y.get())
            scan_x = int(self.v_scan_x.get())
            scan_w = int(self.v_scan_w.get())
        except ValueError:
            self._log("[오류] 숫자를 확인하세요")
            return
        def _run():
            x = find_char_screen_x(char_y, self._char_color, scan_x, scan_w)
            if x is None:
                self._log("[테스트] 색상 못 찾음 — 색상 재저장 또는 Y값 확인")
            else:
                self._log(f"[테스트] 캐릭터 화면 X={x}  "
                          f"(한계: {self.v_bd_left.get()}~{self.v_bd_right.get()})")
        threading.Thread(target=_run, daemon=True).start()

    # ── 토글 ──────────────────────────────────────────────
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
                      f"홀드:{cfg['hold_min']}~{cfg['hold_max']}s")

    def _toggle_natk(self):
        if self.natk.running:
            self.natk.stop()
            self._natk_btn.config(text="▶  평타 ON", bg=BLU)
            self._log("[평타] 비활성화")
        else:
            cfg = self._read_cfg()
            if cfg is None:
                return
            self.natk.start(cfg)
            self._natk_btn.config(text="■  평타 OFF", bg=RED)
            self._log(f"[평타] {cfg['normal_key'].upper()} "
                      f"{cfg['normal_interval']}초마다 {cfg['normal_count']}회")

    def _read_cfg(self):
        try:
            return {
                "attack_key":        self.v_key.get().strip() or "z",
                "hold_min":          float(self.v_hold_min.get()),
                "hold_max":          float(self.v_hold_max.get()),
                "move_min":          float(self.v_move_min.get()),
                "move_max":          float(self.v_move_max.get()),
                "pause_min":         float(self.v_pause_min.get()),
                "pause_max":         float(self.v_pause_max.get()),
                "after_skill_delay": float(self.v_after.get()),
                "boundary_on":       self.v_boundary_on.get(),
                "char_color":        self._char_color,
                "char_y":            int(self.v_char_y.get()),
                "scan_x":            int(self.v_scan_x.get()),
                "scan_w":            int(self.v_scan_w.get()),
                "bd_left":           int(self.v_bd_left.get()),
                "bd_right":          int(self.v_bd_right.get()),
                "normal_key":        self.v_natk_key.get().strip() or "ctrl",
                "normal_interval":   float(self.v_natk_interval.get()),
                "normal_count":      int(self.v_natk_count.get()),
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
        self.natk.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
