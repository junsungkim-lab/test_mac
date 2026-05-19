#!/usr/bin/env python3
"""
메이플랜드 매크로 (Windows/Mac 공용)

동작 방식:
  1. 공격키를 꾹 홀드 (keydown 상태 유지)
  2. 랜덤 시간 후 홀드 해제 → 좌우로 살짝 이동
  3. 다시 공격키 홀드 → 반복

  F8 — ON/OFF 토글
  F9 — 완전 종료
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
_macro_thread = None


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
TOGGLE_KEY = _parse_key(config.TOGGLE_KEY)
QUIT_KEY   = _parse_key(config.QUIT_KEY)

_last_move_dir = "left"


def sleep_interruptible(seconds):
    """stop_event나 running=False 시 즉시 깨어남"""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if not running or stop_event.is_set():
            return False
        time.sleep(0.05)
    return True


def release_attack():
    """공격키가 눌려 있을 경우 안전하게 뗌"""
    try:
        kb.release(ATTACK_KEY)
    except Exception:
        pass


def do_move():
    """좌우 이동: 한 방향으로 갔다가 반대로 복귀"""
    global _last_move_dir

    move_key   = Key.left if _last_move_dir == "left" else Key.right
    return_key = Key.right if _last_move_dir == "left" else Key.left
    _last_move_dir = "right" if _last_move_dir == "left" else "left"

    move_dur   = random.uniform(*config.MOVE_DURATION_RANGE)
    return_dur = random.uniform(*config.RETURN_DURATION_RANGE)

    kb.press(move_key)
    time.sleep(move_dur)
    kb.release(move_key)

    time.sleep(random.uniform(0.05, 0.15))  # 방향 전환 전 짧은 틈

    kb.press(return_key)
    time.sleep(return_dur)
    kb.release(return_key)


def macro_loop():
    global running

    print(f"[매크로] 시작 — 공격키: {config.ATTACK_KEY.upper()}"
          f" | 홀드: {config.HOLD_MIN}~{config.HOLD_MAX}초"
          f" | 토글: {config.TOGGLE_KEY.upper()}"
          f" | 종료: {config.QUIT_KEY.upper()}")

    while running and not stop_event.is_set():

        # ── Phase 1: 공격키 홀드 ──────────────────────────
        hold_time = random.uniform(config.HOLD_MIN, config.HOLD_MAX)
        print(f"  [홀드] {hold_time:.1f}초 동안 {config.ATTACK_KEY.upper()} 홀드")
        kb.press(ATTACK_KEY)

        ok = sleep_interruptible(hold_time)
        kb.release(ATTACK_KEY)

        if not ok:
            break

        # ── Phase 2: 좌우 이동 ────────────────────────────
        print(f"  [이동] {'좌→우' if _last_move_dir == 'left' else '우→좌'} 이동")
        do_move()

        # 이동 후 아주 짧은 딜레이 (0~1초 랜덤)
        pause = random.uniform(*config.PAUSE_AFTER_MOVE)
        if not sleep_interruptible(pause):
            break

    release_attack()
    print("[매크로] 정지됨")


def toggle_macro():
    global running, _macro_thread

    if running:
        running = False
        release_attack()
        print("[매크로] 비활성화 중...")
    else:
        if _macro_thread and _macro_thread.is_alive():
            return
        running = True
        stop_event.clear()
        _macro_thread = threading.Thread(target=macro_loop, daemon=True)
        _macro_thread.start()


def on_press(key):
    try:
        if key == TOGGLE_KEY:
            toggle_macro()
        elif key == QUIT_KEY:
            global running
            running = False
            release_attack()
            stop_event.set()
            print("[매크로] 종료")
            return False
    except Exception:
        pass


def main():
    print("=" * 52)
    print("  메이플랜드 매크로 (맥 전용)")
    print(f"  공격키  : {config.ATTACK_KEY.upper()} (keydown 홀드)")
    print(f"  홀드시간 : {config.HOLD_MIN}~{config.HOLD_MAX}초 (랜덤)")
    print(f"  이동시간 : {config.MOVE_DURATION_RANGE[0]}~{config.MOVE_DURATION_RANGE[1]}초 (랜덤)")
    print(f"  토글    : {config.TOGGLE_KEY.upper()}")
    print(f"  종료    : {config.QUIT_KEY.upper()}")
    print("=" * 52)
    print("게임 창을 앞으로 가져온 뒤 F8을 누르세요.\n")

    try:
        with keyboard.Listener(on_press=on_press) as listener:
            listener.join()
    except Exception as e:
        print(f"\n[오류] {e}")
        print("Windows: python -m pip install pynput 으로 재설치해보세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
