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


# ── 미니맵 노란점 감지 ────────────────────────────────────
def find_char_x_minimap(mm_x, mm_y, mm_w, mm_h, tolerance=30):
    """미니맵에서 노란색 픽셀 X 좌표 반환. 못 찾으면 None."""
    try:
        import pyautogui
        img = pyautogui.screenshot(region=(mm_x, mm_y, mm_w, mm_h))
        pixels = img.load()
        w, h = img.size
        found = []
        for x in range(w):
            for y in range(h):
                r, g, b = pixels[x, y]
                if r > 180 and g > 180 and b < 100:
                    found.append(x)
        return int(sum(found) / len(found)) if found else None
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

            # ── 1. 스킬 홀드 ──────────────────────────────
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

            # ── 3. 경계 확인 (미니맵, 선택사항) ────────────
            forced_dir = None
            if cfg["boundary_on"]:
                char_x = find_char_x_minimap(
                    cfg["mm_x"], cfg["mm_y"],
                    cfg["mm_w"], cfg["mm_h"])
                if char_x is not None:
                    self.log(f"[경계] 미니맵 X={char_x} "
                             f"(허용 {cfg['bd_left']}~{cfg['bd_right']})")
                    if char_x <= cfg["bd_left"]:
                        forced_dir = "right"
                    elif char_x >= cfg["bd_right"]:
                        forced_dir = "left"

            # ── 4. 이동 ───────────────────────────────────
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
                     + (" ← 경계보정" if forced_dir else ""))
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

            # ── 5. 대기 ───────────────────────────────────
            pause = random.uniform(cfg["pause_min"], cfg["pause_max"])
            if pause > 0.05:
                self.log(f"[대기] {pause:.2f}초")
            if not self._sleep(pause):
                break

        self._release()
        self.log("[정지] 매크로 종료")


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
        key = _parse_key(cfg["normal_key"])
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
        self.resizable(True, True)
        self.configure(bg=BG)
        self.engine = MacroEngine(self._log)
        self.natk   = NormalAttackEngine(self._log)
        self._build_ui()
        self._start_hotkey_listener()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 화면 높이에 맞게 창 크기 자동 조정
        self.update_idletasks()
        screen_h = self.winfo_screenheight()
        win_h    = self.winfo_reqheight()
        if win_h > screen_h - 60:
            self.geometry(f"460x{screen_h - 60}")
        else:
            self.geometry(f"460x{win_h}")

    # ── UI 전체 구성 ──────────────────────────────────────
    def _build_ui(self):
        # 스크롤 가능한 캔버스 래퍼
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical",
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # 실제 콘텐츠가 들어가는 내부 프레임
        inner = tk.Frame(canvas, bg=BG)
        win_id = canvas.create_window((0, 0), window=inner,
                                      anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_content_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_content_resize)

        # 마우스 휠 스크롤
        def _on_wheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_wheel)

        # ── 이 아래부터 inner에 위젯 배치 ──────────────────
        # 상태 바
        top = tk.Frame(inner, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 6))
        self._dot = tk.Label(top, text="●", font=("Arial", 20), fg=RED, bg=BG)
        self._dot.pack(side="left")
        self._status = tk.Label(top, text="  정지됨",
                                font=("맑은 고딕", 13, "bold"), fg=FG, bg=BG)
        self._status.pack(side="left")

        # 탭
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=BOX, foreground=GRAY,
                        font=("맑은 고딕", 10, "bold"),
                        padding=[16, 6])
        style.map("TNotebook.Tab",
                  background=[("selected", "#45475a")],
                  foreground=[("selected", FG)])

        nb = ttk.Notebook(inner)
        nb.pack(fill="both", expand=True, padx=10, pady=4)

        tab1 = tk.Frame(nb, bg=BG)
        tab2 = tk.Frame(nb, bg=BG)
        nb.add(tab1, text="  스킬 매크로  ")
        nb.add(tab2, text="  경계 설정  ")

        self._build_tab_macro(tab1)
        self._build_tab_boundary(tab2)

        # inner를 부모로 사용하도록 _hsep에서 쓰는 self 대신 inner 참조
        self._inner = inner

        # 메인 버튼 + 로그 (탭 밖, inner에 배치)
        self._hsep()
        btn_row = tk.Frame(inner, bg=BG)
        btn_row.pack(pady=8)
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

        self._hsep()
        self._log_box = scrolledtext.ScrolledText(
            inner, height=8, width=54,
            bg=BOX, fg=FG, font=("Consolas", 9),
            relief="flat", state="disabled")
        self._log_box.pack(padx=14, pady=(0, 12))

    # ── 탭 1: 스킬 매크로 ────────────────────────────────
    def _build_tab_macro(self, parent):
        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill="x", padx=16, pady=8)

        def f(title, desc, default, row):
            return self._field(frm, title, desc, default, row)

        self.v_key       = f("공격 스킬 키",        "예: z, x, a, v",               "z",   0)
        self._sep(frm, 1)
        self.v_hold_min  = f("홀드 최소 (초)",       "이 시간 이상 스킬키 꾹 누름",   "4",   2)
        self.v_hold_max  = f("홀드 최대 (초)",       "이 시간 이하로 눌렀다가 이동",   "9",   3)
        self._sep(frm, 4)
        self.v_move_min  = f("이동 거리 최소 (초)",  "짧을수록 조금 움직임",           "0.1", 5)
        self.v_move_max  = f("이동 거리 최대 (초)",  "0.2 이하 권장",                 "0.2", 6)
        self._sep(frm, 7)
        self.v_pause_min = f("이동 후 대기 최소 (초)", "이동 끝나고 쉬는 시간",        "0.0", 8)
        self.v_pause_max = f("이동 후 대기 최대 (초)", "0이면 바로 재시작",            "0.5", 9)
        self._sep(frm, 10)
        self.v_after     = f("스킬 후딜레이 (초)",
                             "키 뗀 후 이동 전 대기 → 제자리 복귀 보장",              "0.3", 11)

        # 평타 소구역
        self._hsep(parent)
        tk.Label(parent, text="  매크로 감지 몬스터 처리 (평타)",
                 font=("맑은 고딕", 10, "bold"), fg=BLU, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(parent, text="  스킬과 별개로 주기적으로 평타 키 자동 입력",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        frm2 = tk.Frame(parent, bg=BG)
        frm2.pack(fill="x", padx=16, pady=6)
        self.v_natk_key      = self._field(frm2, "평타 키",      "예: ctrl, x, c", "ctrl", 0)
        self.v_natk_interval = self._field(frm2, "평타 주기 (초)", "몇 초마다 한 번", "60",  1)
        self.v_natk_count    = self._field(frm2, "평타 횟수",    "한 번에 몇 번 연타", "3",  2)

        natk_row = tk.Frame(parent, bg=BG)
        natk_row.pack(pady=(6, 8))
        self._natk_btn = tk.Button(
            natk_row, text="▶  평타 ON",
            font=("맑은 고딕", 10, "bold"), bg=BLU, fg="#1e1e2e",
            relief="flat", padx=16, pady=6, cursor="hand2",
            command=self._toggle_natk)
        self._natk_btn.pack()

    # ── 탭 2: 경계 설정 ──────────────────────────────────
    def _build_tab_boundary(self, parent):
        # ON/OFF 체크박스
        hdr = tk.Frame(parent, bg=BG)
        hdr.pack(fill="x", padx=16, pady=(12, 0))
        tk.Label(hdr, text="경계 이탈 방지",
                 font=("맑은 고딕", 11, "bold"), fg=PUR, bg=BG).pack(side="left")
        self.v_boundary_on = tk.BooleanVar(value=False)
        tk.Checkbutton(hdr, text="사용",
                       variable=self.v_boundary_on,
                       font=("맑은 고딕", 10), fg=FG, bg=BG,
                       selectcolor=BOX, activebackground=BG).pack(side="left", padx=10)

        tk.Label(parent,
                 text="  미니맵(좌상단)에서 내 캐릭터 노란점을 추적해 경계 이탈 시 방향 보정\n"
                      "  노란색 = 내 캐릭터만 해당 (파티원 주황, 타인 빨강) → 오감지 없음",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w", justify="left"
                 ).pack(fill="x", padx=16, pady=(4, 0))

        self._hsep(parent)

        # 미니맵 좌표
        tk.Label(parent, text="  ① 미니맵 영역 좌표 잡기",
                 font=("맑은 고딕", 10, "bold"), fg=FG, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(parent,
                 text="  아래 실시간 좌표를 보면서 미니맵 모서리에 마우스 올리고\n"
                      "  숫자 읽어서 직접 입력하세요",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w", justify="left"
                 ).pack(fill="x", padx=16)

        # 실시간 마우스 좌표 표시
        mouse_frm = tk.Frame(parent, bg=BOX)
        mouse_frm.pack(fill="x", padx=16, pady=6)
        tk.Label(mouse_frm, text=" 현재 마우스 좌표 →",
                 font=("맑은 고딕", 9), fg=GRAY, bg=BOX).pack(side="left", padx=6)
        self._mouse_lbl = tk.Label(mouse_frm, text="X=0   Y=0",
                                   font=("Consolas", 11, "bold"), fg=GRN, bg=BOX)
        self._mouse_lbl.pack(side="left", padx=4, pady=6)
        self._tracking = False
        self._track_btn = tk.Button(mouse_frm, text="▶ 추적 시작",
                                    font=("맑은 고딕", 9), bg=BLU, fg="#1e1e2e",
                                    relief="flat", padx=8, pady=2, cursor="hand2",
                                    command=self._toggle_tracking)
        self._track_btn.pack(side="right", padx=6)

        tk.Label(parent,
                 text="  좌상단 X·Y 읽기 → 입력  /  우하단 X·Y 읽기 → (우X-좌X)=가로, (우Y-좌Y)=세로",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        frm = tk.Frame(parent, bg=BG)
        frm.pack(fill="x", padx=16, pady=4)
        self.v_mm_x = self._field(frm, "미니맵 X",    "미니맵 왼쪽 끝 X",  "0",   0)
        self.v_mm_y = self._field(frm, "미니맵 Y",    "미니맵 위쪽 끝 Y",  "0",   1)
        self.v_mm_w = self._field(frm, "미니맵 가로", "미니맵 너비 (px)",   "200", 2)
        self.v_mm_h = self._field(frm, "미니맵 세로", "미니맵 높이 (px)",   "80",  3)

        # 캡처 미리보기 버튼
        tk.Button(parent, text="🖼  미니맵 캡처 확인 (이미지로 저장해서 확인)",
                  font=("맑은 고딕", 9), bg=BOX, fg=FG,
                  relief="flat", padx=8, pady=4, cursor="hand2",
                  command=self._preview_minimap
                  ).pack(pady=(0, 4))

        self._hsep(parent)

        # 한계선
        tk.Label(parent, text="  ② 이동 허용 범위 (미니맵 내 X 픽셀)",
                 font=("맑은 고딕", 10, "bold"), fg=FG, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(parent,
                 text="  캐릭터를 왼쪽 끝/오른쪽 끝에 세우고 아래 테스트 버튼으로 X값 확인",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        frm2 = tk.Frame(parent, bg=BG)
        frm2.pack(fill="x", padx=16, pady=4)
        self.v_bd_left  = self._field(frm2, "왼쪽 한계 X",
                                      "이 값 이하면 강제 오른쪽 이동", "20",  0)
        self.v_bd_right = self._field(frm2, "오른쪽 한계 X",
                                      "이 값 이상이면 강제 왼쪽 이동", "180", 1)

        self._hsep(parent)

        # 테스트 버튼
        tk.Label(parent, text="  ③ 감지 테스트",
                 font=("맑은 고딕", 10, "bold"), fg=FG, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(parent,
                 text="  게임 실행 중에 버튼 누르면 현재 캐릭터 X 좌표를 로그에 출력",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        tk.Button(parent, text="📍  현재 위치 테스트",
                  font=("맑은 고딕", 10), bg=BOX, fg=FG,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._test_pos).pack(pady=10)

    # ── 공통 위젯 헬퍼 ───────────────────────────────────
    def _field(self, parent, title, desc, default, row):
        tk.Label(parent, text=title, font=("맑은 고딕", 10, "bold"),
                 fg=FG, bg=BG, anchor="w").grid(
            row=row*2, column=0, sticky="w", pady=(8, 0))
        tk.Label(parent, text=desc, font=("맑은 고딕", 8),
                 fg=GRAY, bg=BG, anchor="w").grid(
            row=row*2+1, column=0, sticky="w")
        var = tk.StringVar(value=default)
        tk.Entry(parent, textvariable=var, width=8,
                 bg=BOX, fg=FG, insertbackground=FG,
                 relief="flat", font=("Consolas", 10)).grid(
            row=row*2, column=1, rowspan=2, padx=(16, 0), sticky="w")
        return var

    def _sep(self, parent, row):
        tk.Frame(parent, bg="#45475a", height=1).grid(
            row=row*2, column=0, columnspan=2, sticky="ew", pady=4)

    def _hsep(self, parent=None):
        target = parent if parent else self._inner
        tk.Frame(target, bg="#45475a", height=1).pack(fill="x", padx=10, pady=4)

    # ── 로그 ─────────────────────────────────────────────
    def _log(self, msg):
        ts = time.strftime("%H:%M:%S")
        def _w():
            self._log_box.config(state="normal")
            self._log_box.insert("end", f"[{ts}] {msg}\n")
            self._log_box.see("end")
            self._log_box.config(state="disabled")
        self.after(0, _w)

    # ── 실시간 마우스 좌표 추적 ──────────────────────────
    def _toggle_tracking(self):
        self._tracking = not self._tracking
        if self._tracking:
            self._track_btn.config(text="■ 추적 중지", bg=RED)
            self._update_mouse_pos()
        else:
            self._track_btn.config(text="▶ 추적 시작", bg=BLU)

    def _update_mouse_pos(self):
        if not self._tracking:
            return
        try:
            import pyautogui
            x, y = pyautogui.position()
            self._mouse_lbl.config(text=f"X={x}   Y={y}")
        except Exception as e:
            self._mouse_lbl.config(text=f"오류: {e}")
            self._tracking = False
            self._track_btn.config(text="▶ 추적 시작", bg=BLU)
            return
        self.after(100, self._update_mouse_pos)

    # ── 미니맵 캡처 미리보기 ─────────────────────────────
    def _preview_minimap(self):
        try:
            mm_x = int(self.v_mm_x.get())
            mm_y = int(self.v_mm_y.get())
            mm_w = int(self.v_mm_w.get())
            mm_h = int(self.v_mm_h.get())
        except ValueError:
            self._log("[오류] 좌표 숫자를 확인하세요")
            return
        if mm_w <= 0 or mm_h <= 0:
            self._log("[오류] 가로/세로가 0 이하입니다. 좌표를 다시 확인하세요")
            return
        def _run():
            try:
                import pyautogui, os
                img = pyautogui.screenshot(region=(mm_x, mm_y, mm_w, mm_h))
                img = img.resize((mm_w * 4, mm_h * 4))
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "minimap_preview.png")
                img.save(path)
                self._log(f"[미리보기] 저장: {path}")
                os.startfile(path)
            except ImportError:
                self._log("[오류] pyautogui 미설치 → pip install pyautogui pillow")
            except Exception as e:
                self._log(f"[오류] {e}")
        threading.Thread(target=_run, daemon=True).start()

    # ── 위치 테스트 ───────────────────────────────────────
    def _test_pos(self):
        try:
            mm_x = int(self.v_mm_x.get())
            mm_y = int(self.v_mm_y.get())
            mm_w = int(self.v_mm_w.get())
            mm_h = int(self.v_mm_h.get())
        except ValueError:
            self._log("[오류] 미니맵 좌표를 숫자로 입력하세요")
            return
        def _run():
            x = find_char_x_minimap(mm_x, mm_y, mm_w, mm_h)
            if x is None:
                self._log("[테스트] 노란점 못 찾음 — 미니맵 좌표 확인 필요")
            else:
                self._log(f"[테스트] 캐릭터 미니맵 X={x}  "
                          f"(설정 한계: {self.v_bd_left.get()}~{self.v_bd_right.get()})")
        threading.Thread(target=_run, daemon=True).start()

    # ── 토글 ─────────────────────────────────────────────
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
                      f"홀드:{cfg['hold_min']}~{cfg['hold_max']}s  "
                      f"경계:{'ON' if cfg['boundary_on'] else 'OFF'}")

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
                "normal_key":        self.v_natk_key.get().strip() or "ctrl",
                "normal_interval":   float(self.v_natk_interval.get()),
                "normal_count":      int(self.v_natk_count.get()),
                "boundary_on":       self.v_boundary_on.get(),
                "mm_x":              int(self.v_mm_x.get()),
                "mm_y":              int(self.v_mm_y.get()),
                "mm_w":              int(self.v_mm_w.get()),
                "mm_h":              int(self.v_mm_h.get()),
                "bd_left":           int(self.v_bd_left.get()),
                "bd_right":          int(self.v_bd_right.get()),
            }
        except ValueError:
            self._log("[오류] 숫자를 올바르게 입력하세요")
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
