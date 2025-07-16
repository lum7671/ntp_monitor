#!/bin/bash

# NTP Monitor 설정 파일 설치 스크립트

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXAMPLE_CONFIG="$SCRIPT_DIR/ntp_monitor.conf.example"

echo "NTP Monitor 설정 파일 설치"
echo "=========================="

# 사용자 홈 디렉토리에 설치
USER_CONFIG="$HOME/.ntp_monitor.conf"
if [ ! -f "$USER_CONFIG" ]; then
  echo "사용자 설정 파일 생성: $USER_CONFIG"
  cp "$EXAMPLE_CONFIG" "$USER_CONFIG"
  echo "✓ 사용자 설정 파일이 생성되었습니다."
else
  echo "ℹ 사용자 설정 파일이 이미 존재합니다: $USER_CONFIG"
fi

# 시스템 전역 설치 (root 권한 필요)
SYSTEM_CONFIG="/etc/ntp_monitor.conf"
if [ "$EUID" -eq 0 ]; then
  if [ ! -f "$SYSTEM_CONFIG" ]; then
    echo "시스템 설정 파일 생성: $SYSTEM_CONFIG"
    cp "$EXAMPLE_CONFIG" "$SYSTEM_CONFIG"
    chmod 644 "$SYSTEM_CONFIG"
    echo "✓ 시스템 설정 파일이 생성되었습니다."
  else
    echo "ℹ 시스템 설정 파일이 이미 존재합니다: $SYSTEM_CONFIG"
  fi
else
  echo "⚠ 시스템 설정 파일 설치를 위해서는 root 권한이 필요합니다."
  echo "  sudo $0 를 실행하여 /etc/ntp_monitor.conf를 설치할 수 있습니다."
fi

echo ""
echo "설정 파일 우선순위:"
echo "1. $USER_CONFIG (사용자 설정)"
echo "2. $SYSTEM_CONFIG (시스템 설정)"
echo ""
echo "설정을 변경한 후 ntp-monitor를 실행하세요."
