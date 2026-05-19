#!/bin/bash
# 메이플랜드 매크로 의존성 설치

echo "=== 매크로 설치 시작 ==="

# Python3 확인
if ! command -v python3 &>/dev/null; then
    echo "[오류] python3가 없습니다. https://python.org 에서 설치하세요."
    exit 1
fi

echo "Python: $(python3 --version)"

# pip 최신화 후 pynput 설치
python3 -m pip install --upgrade pip --quiet
python3 -m pip install pynput --quiet

echo ""
echo "=== 설치 완료 ==="
echo ""
echo "실행 방법:"
echo "  python3 macro.py"
echo ""
echo "주의: 처음 실행 시 macOS 손쉬운 사용 권한이 필요합니다."
echo "  시스템 설정 → 개인정보 보호 및 보안 → 손쉬운 사용"
echo "  → 터미널(또는 Python) 추가"
