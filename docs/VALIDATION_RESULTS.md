# Validation Results

## 실행 정보

- 날짜: 2026-05-29
- 범위: 1차(에러 수정 + 최소 리팩토링)
- 실행 환경: macOS 개발 환경, Python 3.x

## 실행 명령

- PYTHONPATH=src python3 -m ntp_monitor.main
- PYTHONPATH=src python3 inline script (setup_logger 케이스별 검증)

## 케이스별 결과

1. syslog_address = /dev/log

- 결과: PASS
- 메모: 환경에 따라 /dev/log 미존재 시 자동 fallback 동작

1. syslog_address = /tmp/not_exists_ntp_socket

- 결과: PASS
- 메모: 유효하지 않은 unix socket 경로를 건너뛰고 fallback 동작

1. syslog_address = localhost:514

- 결과: PASS
- 메모: host:port 파싱 후 네트워크 syslog 후보로 처리

1. syslog_address = invalid-address

- 결과: PASS
- 메모: 잘못된 문자열 주소는 직접 핸들러 생성하지 않고 fallback 동작

## 공통 검증 포인트

- 네 케이스 모두 실행 종료 코드 0
- 실행 중 '--- Logging error ---' traceback 미발생

## 미검증 항목

- 실제 DietPi 운영 환경에서 /run/systemd/journal/dev-log 사용 경로의 실기기 확인
- rsyslog/journald 상태에 따른 syslog 수신 여부(기능적 수집 확인)

## 결론

1차 목표(내부 logging traceback 제거, 안전 fallback)는 달성되었습니다. 운영 반영 전에는 DietPi 실환경에서 미검증 항목 2가지를 추가 확인하는 것을 권장합니다.

## 로그 고도화 검증 (2026-05-29)

### 시나리오

- threshold = 1.0
- consecutive_warning_threshold = 3
- critical_jitter_multiplier = 2.0
- 실행 시퀀스: 1.1 -> 1.2 -> 1.3 -> 0.8 -> 2.1

### 결과

1. RUN1: WARNING 발생
1. RUN2: WARNING 발생
1. RUN3: WARNING 발생 후 "연속 3회" ERROR 1회 발생
1. RUN4: INFO(정상) 발생 및 연속 카운트 리셋
1. RUN5: WARNING 발생 후 "2배 초과" 즉시 ERROR 1회 발생

### 상태 파일 검증

- 최종 상태: consecutive_warnings=0
- warning_jitters=[]
- 연속 경고/즉시 에러 후 상태 리셋 정상
