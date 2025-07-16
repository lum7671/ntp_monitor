#!/bin/bash

# NTP Monitor 실행을 위한 래퍼 스크립트
# 이 스크립트는 cron에서 PATH 문제 없이 ntp_monitor를 실행하기 위해 사용됩니다.

# PATH 설정 (사용자 환경에 맞게 조정)
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

# 로그 파일 설정 (선택사항)
# LOGFILE="$HOME/.ntp_monitor.log"

# ntp_monitor 실행
# 로그 파일로 출력하려면 다음 라인의 주석을 해제하세요:
# ntp_monitor >> "$LOGFILE" 2>&1

ntp_monitor
