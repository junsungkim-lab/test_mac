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


# ── 스크린샷 (DirectX 게임 호환) ─────────────────────────
def _grab(x, y, w, h):
    """mss → PIL.ImageGrab 순서로 시도. 둘 다 실패하면 None."""
    try:
        import mss, mss.tools
        from PIL import Image
        with mss.mss() as sct:
            mon = {"left": x, "top": y, "width": w, "height": h}
            raw = sct.grab(mon)
            return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
    except Exception:
        pass
    try:
        from PIL import ImageGrab
        return ImageGrab.grab(bbox=(x, y, x + w, y + h))
    except Exception:
        return None


# ── 미니맵 노란점 감지 ────────────────────────────────────
def find_char_x_minimap(mm_x, mm_y, mm_w, mm_h, tolerance=30):
    """미니맵에서 노란색 픽셀 X 좌표 반환. 못 찾으면 None."""
    try:
        img = _grab(mm_x, mm_y, mm_w, mm_h)
        if img is None:
            return None
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
                    center = cfg.get("center_x", 0)
                    buf    = cfg["bd_buffer"]
                    if center > 0:
                        # 중앙 기준: 항상 중앙 방향으로 이동 → 절대 끝으로 안 감
                        forced_dir = "right" if char_x <= center else "left"
                        self.log(f"[경계] 미니맵 X={char_x}  중앙={center} → {'→' if forced_dir=='right' else '←'}")
                    else:
                        # 버퍼 방식 (center_x=0 일 때 유지)
                        self.log(f"[경계] 미니맵 X={char_x} "
                                 f"(안전구역 {cfg['bd_left']+buf}~{cfg['bd_right']-buf})")
                        if char_x <= cfg["bd_left"] + buf:
                            forced_dir = "right"
                        elif char_x >= cfg["bd_right"] - buf:
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


# ── 화면 감시 엔진 ───────────────────────────────────────────
class ScreenWatcher:
    """검정화면(마을 이동) 감지 + 거짓말탐지기 자동 클릭"""

    def __init__(self, log_fn, stop_macro_fn):
        self.log = log_fn
        self.stop_macro = stop_macro_fn
        self.running = False
        self._stop = threading.Event()
        self._thread = None
        self._lie_cooldown = 0

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

    # ── 내부 루프 ─────────────────────────────────────────
    def _loop(self):
        _black_hits = 0          # 연속 검정화면 카운트
        _lie_tick   = 0          # 거짓말탐지기는 3틱(≈0.45s)마다 체크
        while self.running and not self._stop.is_set():
            try:
                cfg = self._cfg
                # 검정화면: 0.15s마다, 2회 연속이면 발동
                if cfg.get("black_on"):
                    img = _grab(cfg["watch_x"], cfg["watch_y"],
                                cfg["watch_w"], cfg["watch_h"])
                    if img is not None:
                        b = self._brightness(img)
                        if b < cfg["black_thresh"]:
                            _black_hits += 1
                            if _black_hits >= 2:
                                self.log(f"[감시] 검정화면 확인 (밝기={b:.0f}) → 매크로 정지")
                                self.stop_macro()
                                _black_hits = 0
                                time.sleep(3)
                        else:
                            _black_hits = 0
                # 거짓말탐지기: 3틱(≈0.45s)마다
                _lie_tick += 1
                if cfg.get("lie_on") and _lie_tick >= 3 and time.time() > self._lie_cooldown:
                    _lie_tick = 0
                    self._check_lie(cfg)
            except Exception as e:
                self.log(f"[감시오류] {e}")
            time.sleep(0.15)

    # ── 공통 유틸 ─────────────────────────────────────────
    @staticmethod
    def _brightness(img):
        pix = list(img.convert("L").getdata())
        return sum(pix) / len(pix)

    @staticmethod
    def _img_vec(img, size=(32, 32)):
        return list(img.resize(size).convert("L").getdata())

    @staticmethod
    def _diff(a, b):
        return sum(abs(x - y) for x, y in zip(a, b))

    @staticmethod
    def _click(x, y):
        try:
            import ctypes
            ctypes.windll.user32.SetCursorPos(x, y)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
            return
        except Exception:
            pass
        try:
            from pynput.mouse import Button, Controller as MC
            mc = MC()
            mc.position = (x, y)
            time.sleep(0.05)
            mc.click(Button.left)
        except Exception:
            pass

    # ── 검정화면 감지 ─────────────────────────────────────
    def _check_black(self, cfg):
        img = _grab(cfg["watch_x"], cfg["watch_y"],
                    cfg["watch_w"], cfg["watch_h"])
        if img is None:
            return
        b = self._brightness(img)
        if b < cfg["black_thresh"]:
            self.log(f"[감시] 검정화면 감지 (밝기={b:.0f}) → 매크로 전체 정지")
            self.stop_macro()
            time.sleep(3)  # 화면 전환이 끝날 때까지 재감지 방지

    # ── 거짓말탐지기 감지 ─────────────────────────────────
    def _check_lie(self, cfg):
        # 팝업 영역 밝기가 임계값보다 높아야 팝업이 열린 것으로 판단
        pop = _grab(cfg["lie_pop_x"], cfg["lie_pop_y"],
                    cfg["lie_pop_w"], cfg["lie_pop_h"])
        if pop is None:
            return
        if self._brightness(pop) < cfg.get("lie_pop_thresh", 150):
            return

        self.log("[감시] 거짓말탐지기 감지! 정답 찾는 중...")

        sample = _grab(cfg["lie_sample_x"], cfg["lie_sample_y"],
                       cfg["lie_sample_w"], cfg["lie_sample_h"])
        if sample is None:
            return

        n = cfg["lie_btn_count"]
        bx = cfg["lie_btn_x"]
        by = cfg["lie_btn_y"]
        bw = cfg["lie_btn_w"]
        bh = cfg["lie_btn_h"]
        each_w = bw // n
        ref = self._img_vec(sample)

        best_score, best_idx = float("inf"), 0
        for i in range(n):
            btn = _grab(bx + i * each_w, by, each_w, bh)
            if btn is None:
                continue
            score = self._diff(ref, self._img_vec(btn))
            self.log(f"  버튼{i+1} 유사도차이={score:.0f}")
            if score < best_score:
                best_score, best_idx = score, i

        cx = bx + best_idx * each_w + each_w // 2
        cy = by + bh // 2
        self.log(f"[감시] 버튼 {best_idx+1} 클릭 (X={cx} Y={cy})")
        self._click(cx, cy)
        self._lie_cooldown = time.time() + 15  # 15초 쿨다운


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
        self.engine  = MacroEngine(self._log)
        self.natk    = NormalAttackEngine(self._log)
        self.watcher = ScreenWatcher(self._log, self._stop_all)
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
        tab3 = tk.Frame(nb, bg=BG)
        nb.add(tab1, text="  스킬 매크로  ")
        nb.add(tab2, text="  경계 설정  ")
        nb.add(tab3, text="  화면 감시  ")

        self._build_tab_macro(tab1)
        self._build_tab_boundary(tab2)
        self._build_tab_watcher(tab3)

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
        self.v_bd_left   = self._field(frm2, "왼쪽 한계 X",
                                       "이 값 이하면 강제 오른쪽 이동", "20",  0)
        self.v_bd_right  = self._field(frm2, "오른쪽 한계 X",
                                       "이 값 이상이면 강제 왼쪽 이동", "180", 1)
        self.v_bd_buffer = self._field(frm2, "안전 여유 (px)",
                                       "한계보다 이 값만큼 미리 방향 전환 → 이탈 방지", "15", 2)
        self.v_center_x  = self._field(frm2, "중앙 X 좌표 (권장)",
                                       "0 이면 위 한계값 방식 사용. 설정하면 항상 중앙으로 수렴", "0", 3)

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

    # ── 탭 3: 화면 감시 ──────────────────────────────────
    def _build_tab_watcher(self, parent):
        # ① 검정화면 감지
        tk.Label(parent, text="  ① 검정화면 감지 (마을 이동 시 자동 정지)",
                 font=("맑은 고딕", 10, "bold"), fg=FG, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(parent,
                 text="  마을 이동 시 검정화면 → 밝기가 임계값 미만이면 매크로 정지",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        self.v_black_on = tk.BooleanVar(value=True)
        tk.Checkbutton(parent, text=" 검정화면 감지 사용",
                       variable=self.v_black_on,
                       bg=BG, fg=FG, selectcolor=BOX,
                       activebackground=BG, activeforeground=FG,
                       font=("맑은 고딕", 10)
                       ).pack(anchor="w", padx=16, pady=(4, 0))

        frm_b = tk.Frame(parent, bg=BG)
        frm_b.pack(fill="x", padx=16, pady=4)
        self.v_watch_x = self._field(frm_b, "감시 영역 X",  "게임 화면 왼쪽 X", "0",   0)
        self.v_watch_y = self._field(frm_b, "감시 영역 Y",  "게임 화면 위쪽 Y", "0",   1)
        self.v_watch_w = self._field(frm_b, "감시 영역 W",  "가로 픽셀 수",     "800", 2)
        self.v_watch_h = self._field(frm_b, "감시 영역 H",  "세로 픽셀 수",     "600", 3)
        self.v_black_thresh = self._field(frm_b, "밝기 임계값",
                                          "0~255, 이 값 미만이면 검정화면", "20", 4)

        tk.Button(parent, text="📷  현재 밝기 확인",
                  font=("맑은 고딕", 10), bg=BOX, fg=FG,
                  relief="flat", padx=14, pady=6, cursor="hand2",
                  command=self._test_brightness).pack(pady=(6, 2))

        self._hsep(parent)

        # ② 거짓말탐지기
        tk.Label(parent, text="  ② 거짓말탐지기 자동 클릭",
                 font=("맑은 고딕", 10, "bold"), fg=FG, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16, pady=(8, 0))
        tk.Label(parent,
                 text="  팝업 감지 → 샘플 문자와 가장 유사한 버튼 자동 클릭 (15초 쿨다운)",
                 font=("맑은 고딕", 8), fg=GRAY, bg=BG, anchor="w"
                 ).pack(fill="x", padx=16)

        self.v_lie_on = tk.BooleanVar(value=False)
        tk.Checkbutton(parent, text=" 거짓말탐지기 감지 사용",
                       variable=self.v_lie_on,
                       bg=BG, fg=FG, selectcolor=BOX,
                       activebackground=BG, activeforeground=FG,
                       font=("맑은 고딕", 10)
                       ).pack(anchor="w", padx=16, pady=(4, 0))

        frm_l = tk.Frame(parent, bg=BG)
        frm_l.pack(fill="x", padx=16, pady=4)

        # 팝업 감지 영역
        tk.Label(frm_l, text="─ 팝업 감지 영역 (팝업 전체)",
                 font=("맑은 고딕", 9, "bold"), fg=BLU, bg=BG, anchor="w"
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.v_lie_pop_x = self._field(frm_l, "팝업 X", "팝업 왼쪽 X",  "400", 1)
        self.v_lie_pop_y = self._field(frm_l, "팝업 Y", "팝업 위쪽 Y",  "250", 2)
        self.v_lie_pop_w = self._field(frm_l, "팝업 W", "팝업 가로 크기", "300", 3)
        self.v_lie_pop_h = self._field(frm_l, "팝업 H", "팝업 세로 크기", "200", 4)
        self.v_lie_pop_thresh = self._field(frm_l, "밝기 임계값",
                                            "이 값 초과여야 팝업 열린 것으로 판단", "150", 5)

        # 샘플 문자 영역
        tk.Label(frm_l, text="─ 샘플 문자 영역 (탐지기에 표시된 '정답 문자')",
                 font=("맑은 고딕", 9, "bold"), fg=PUR, bg=BG, anchor="w"
                 ).grid(row=12, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.v_lie_sample_x = self._field(frm_l, "샘플 X", "정답 문자 왼쪽 X",  "440", 7)
        self.v_lie_sample_y = self._field(frm_l, "샘플 Y", "정답 문자 위쪽 Y",  "280", 8)
        self.v_lie_sample_w = self._field(frm_l, "샘플 W", "정답 문자 가로 크기", "50",  9)
        self.v_lie_sample_h = self._field(frm_l, "샘플 H", "정답 문자 세로 크기", "50",  10)

        # 버튼 영역
        tk.Label(frm_l, text="─ 선택 버튼 전체 영역 (클릭 가능한 보기들)",
                 font=("맑은 고딕", 9, "bold"), fg=GRN, bg=BG, anchor="w"
                 ).grid(row=22, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.v_lie_btn_x = self._field(frm_l, "버튼 X", "버튼 영역 왼쪽 X",  "410", 12)
        self.v_lie_btn_y = self._field(frm_l, "버튼 Y", "버튼 영역 위쪽 Y",  "360", 13)
        self.v_lie_btn_w = self._field(frm_l, "버튼 W", "버튼 영역 전체 가로", "250", 14)
        self.v_lie_btn_h = self._field(frm_l, "버튼 H", "버튼 영역 세로",     "50",  15)
        self.v_lie_btn_count = self._field(frm_l, "버튼 개수", "선택지 총 개수", "5",  16)

        self._hsep(parent)

        # 감시 시작/중지 버튼
        self._watch_btn = tk.Button(
            parent, text="👁  감시 시작",
            font=("맑은 고딕", 11, "bold"), bg=BLU, fg="#1e1e2e",
            relief="flat", padx=20, pady=8, cursor="hand2",
            command=self._toggle_watcher)
        self._watch_btn.pack(pady=8)

    # ── 화면 감시 토글 ────────────────────────────────────
    def _toggle_watcher(self):
        if self.watcher.running:
            self.watcher.stop()
            self._watch_btn.config(text="👁  감시 시작", bg=BLU)
            self._log("[감시] 화면 감시 중지")
        else:
            cfg = self._read_watcher_cfg()
            if cfg is None:
                return
            self.watcher.start(cfg)
            self._watch_btn.config(text="■  감시 중지", bg=RED)
            modes = []
            if cfg["black_on"]:
                modes.append("검정화면")
            if cfg["lie_on"]:
                modes.append("거짓말탐지기")
            self._log(f"[감시] 시작 ({', '.join(modes) or '비활성'})")

    def _read_watcher_cfg(self):
        try:
            return {
                "black_on":       self.v_black_on.get(),
                "watch_x":        int(self.v_watch_x.get()),
                "watch_y":        int(self.v_watch_y.get()),
                "watch_w":        int(self.v_watch_w.get()),
                "watch_h":        int(self.v_watch_h.get()),
                "black_thresh":   int(self.v_black_thresh.get()),
                "lie_on":         self.v_lie_on.get(),
                "lie_pop_x":      int(self.v_lie_pop_x.get()),
                "lie_pop_y":      int(self.v_lie_pop_y.get()),
                "lie_pop_w":      int(self.v_lie_pop_w.get()),
                "lie_pop_h":      int(self.v_lie_pop_h.get()),
                "lie_pop_thresh": int(self.v_lie_pop_thresh.get()),
                "lie_sample_x":   int(self.v_lie_sample_x.get()),
                "lie_sample_y":   int(self.v_lie_sample_y.get()),
                "lie_sample_w":   int(self.v_lie_sample_w.get()),
                "lie_sample_h":   int(self.v_lie_sample_h.get()),
                "lie_btn_x":      int(self.v_lie_btn_x.get()),
                "lie_btn_y":      int(self.v_lie_btn_y.get()),
                "lie_btn_w":      int(self.v_lie_btn_w.get()),
                "lie_btn_h":      int(self.v_lie_btn_h.get()),
                "lie_btn_count":  int(self.v_lie_btn_count.get()),
            }
        except ValueError:
            self._log("[오류] 화면 감시 탭 숫자를 올바르게 입력하세요")
            return None

    def _test_brightness(self):
        def _run():
            try:
                x, y = int(self.v_watch_x.get()), int(self.v_watch_y.get())
                w, h = int(self.v_watch_w.get()), int(self.v_watch_h.get())
                img = _grab(x, y, w, h)
                if img is None:
                    self._log("[감시] 캡처 실패")
                    return
                pix = list(img.convert("L").getdata())
                b = sum(pix) / len(pix)
                self._log(f"[감시] 현재 밝기={b:.1f}  (임계값={self.v_black_thresh.get()} 미만이면 검정화면)")
            except Exception as e:
                self._log(f"[감시] 오류: {e}")
        threading.Thread(target=_run, daemon=True).start()

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
            import mss
            with mss.mss() as sct:
                x, y = sct.monitors[0]["left"], sct.monitors[0]["top"]
            # mss로 마우스 위치 못 가져오므로 ctypes 사용 (Windows)
            import ctypes
            pt = ctypes.wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            self._mouse_lbl.config(text=f"X={pt.x}   Y={pt.y}")
        except Exception:
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
                import os
                img = _grab(mm_x, mm_y, mm_w, mm_h)
                if img is None:
                    self._log("[오류] 캡처 실패 — pip install mss pillow 확인")
                    return
                img = img.resize((mm_w * 4, mm_h * 4))
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "minimap_preview.png")
                img.save(path)
                self._log(f"[미리보기] 저장됨 → {path}")
                os.startfile(path)
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
                "bd_buffer":         int(self.v_bd_buffer.get()),
                "center_x":          int(self.v_center_x.get()),
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

    def _stop_all(self):
        """검정화면 감지 시 콜백 — 매크로+평타 즉시 정지"""
        if self.engine.running:
            self.engine.stop()
            self.after(0, lambda: (
                self._dot.config(fg=RED),
                self._status.config(text="  정지됨 (화면감지)"),
                self._btn.config(text="▶   시 작   (F8)", bg=GRN),
            ))
        if self.natk.running:
            self.natk.stop()
            self.after(0, lambda: self._natk_btn.config(
                text="▶  평타 ON", bg=BLU))

    def _on_close(self):
        self.engine.stop()
        self.natk.stop()
        self.watcher.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
