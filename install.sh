#!/bin/bash
# 메이플랜드 매크로 원클릭 설치 스크립트
# 사용법: bash install.sh

set -e

INSTALL_DIR="$HOME/macro"

echo "=================================================="
echo "  메이플랜드 매크로 설치"
echo "=================================================="

# 1. 디렉토리 생성
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# 2. Python3 확인
if ! command -v python3 &>/dev/null; then
    echo "[오류] python3가 없습니다."
    echo "https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요."
    exit 1
fi
echo "[OK] Python: $(python3 --version)"

# 3. pynput 설치
echo "[설치중] pynput..."
python3 -m pip install pynput --quiet
echo "[OK] pynput 설치 완료"

# 4. config.py 생성
cat > "$INSTALL_DIR/config.py" << 'PYEOF'
# ─────────────────────────────────────────────
#  메이플랜드 매크로 설정
# ─────────────────────────────────────────────

ATTACK_KEY = "z"          # 누를 공격 키
MIN_INTERVAL = 0.15       # 최소 간격 (초)
MAX_INTERVAL = 0.85       # 최대 간격 (초)

MOVE_ENABLED = True       # 좌우 이동 사용 여부
MOVE_EVERY_SEC = 12       # 몇 초마다 이동 (랜덤 ±3초)
MOVE_DURATION = 0.25      # 이동 키 누르는 시간 (초)
MOVE_RETURN_DELAY = 0.2   # 반대 방향 복귀 지연

TOGGLE_KEY = "f8"         # 매크로 ON/OFF 토글
QUIT_KEY = "f9"           # 완전 종료

KEY_HOLD_DURATION = 0.08  # 키 홀드 시간
PYEOF

# 5. macro.py 생성
cat > "$INSTALL_DIR/macro.py" << 'PYEOF'
#!/usr/bin/env python3
"""
메이플랜드 맥 전용 매크로
  F8  — 매크로 ON/OFF 토글
  F9  — 완전 종료
"""

import time
import random
import threading
import sys
from pynput import keyboard
from pynput.keyboard import Key, Controller

import config

kb = Controller()
running = False
stop_event = threading.Event()
_last_move_dir = "left"


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


ATTACK_KEY = _parse_key(config.ATTACK_KEY)
TOGGLE_KEY  = _parse_key(config.TOGGLE_KEY)
QUIT_KEY    = _parse_key(config.QUIT_KEY)


def press_key(key, hold=None):
    duration = hold if hold is not None else config.KEY_HOLD_DURATION
    kb.press(key)
    time.sleep(duration)
    kb.release(key)


def do_side_move():
    global _last_move_dir
    if _last_move_dir == "left":
        press_key(Key.left, config.MOVE_DURATION)
        time.sleep(config.MOVE_RETURN_DELAY)
        press_key(Key.right, config.MOVE_DURATION)
        _last_move_dir = "right"
    else:
        press_key(Key.right, config.MOVE_DURATION)
        time.sleep(config.MOVE_RETURN_DELAY)
        press_key(Key.left, config.MOVE_DURATION)
        _last_move_dir = "left"


def _next_move_interval():
    return max(5.0, config.MOVE_EVERY_SEC + random.uniform(-3, 3))


def macro_loop():
    global running
    next_move_at = time.time() + _next_move_interval()
    print("[매크로] 시작됨 — 공격키:", config.ATTACK_KEY.upper(),
          "| 토글:", config.TOGGLE_KEY.upper(),
          "| 종료:", config.QUIT_KEY.upper())

    while running and not stop_event.is_set():
        now = time.time()
        if config.MOVE_ENABLED and now >= next_move_at:
            do_side_move()
            next_move_at = now + _next_move_interval()
            time.sleep(0.1)

        if running:
            press_key(ATTACK_KEY)

        deadline = time.time() + random.uniform(config.MIN_INTERVAL, config.MAX_INTERVAL)
        while time.time() < deadline:
            if not running or stop_event.is_set():
                break
            time.sleep(0.05)

    print("[매크로] 정지됨")


_macro_thread = None


def toggle_macro():
    global running, _macro_thread
    if running:
        running = False
        print("[매크로] 비활성화 중...")
    else:
        if _macro_thread and _macro_thread.is_alive():
            return
        running = True
        _macro_thread = threading.Thread(target=macro_loop, daemon=True)
        _macro_thread.start()


def on_press(key):
    try:
        if key == TOGGLE_KEY:
            toggle_macro()
        elif key == QUIT_KEY:
            global running
            running = False
            stop_event.set()
            print("[매크로] 종료")
            return False
    except Exception:
        pass


def main():
    print("=" * 50)
    print("  메이플랜드 매크로 (맥 전용)")
    print(f"  공격키  : {config.ATTACK_KEY.upper()}")
    print(f"  간격    : {config.MIN_INTERVAL}~{config.MAX_INTERVAL}초 (랜덤)")
    print(f"  좌우이동: {'ON' if config.MOVE_ENABLED else 'OFF'} (매 ~{config.MOVE_EVERY_SEC}초)")
    print(f"  토글    : {config.TOGGLE_KEY.upper()}")
    print(f"  종료    : {config.QUIT_KEY.upper()}")
    print("=" * 50)
    print("게임 창을 앞으로 가져온 뒤 F8을 누르세요.\n")

    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except Exception as e:
        print(f"\n[오류] {e}")
        print("시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용에서")
        print("터미널 및 python3 에 접근성 권한을 부여하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
PYEOF

chmod +x "$INSTALL_DIR/macro.py"

echo ""
echo "=================================================="
echo "  설치 완료!  설치 위치: $INSTALL_DIR"
echo "=================================================="
echo ""
echo "다음 단계 (필수 — 최초 1회):"
echo "  1. 아래 명령어로 손쉬운 사용 설정 열기:"
echo "     open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'"
echo ""
echo "  2. 잠금 해제 후 [+] 버튼 클릭"
echo "     /usr/bin/python3  추가 후 토글 ON"
echo "     Terminal.app 도 추가 후 토글 ON"
echo ""
echo "  3. 터미널 완전 종료(Cmd+Q) 후 재시작"
echo ""
echo "실행 방법:"
echo "  python3 ~/macro/macro.py"
echo ""

# 손쉬운 사용 설정 자동으로 열기
open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility" 2>/dev/null || true
