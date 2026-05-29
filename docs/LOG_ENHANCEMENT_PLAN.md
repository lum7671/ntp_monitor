# 로그 고도화 계획 및 구현 문서

## 목적

기존 warning 기반 모니터링은 유지하면서, 운영 알림 품질을 높이기 위해 아래 2가지 규칙을 추가합니다.

1. 지터가 임계값 초과인 warning이 3회 연속 발생하면 error 로그 발송
1. 지터가 임계값의 2배 이상이면 즉시 error 로그 발송

syslog에서 error 로그가 메일로 연동되는 운영 환경을 전제로 합니다.

## 정책

1. 정상값(임계값 이하) 1회 발생 시 연속 warning 카운트는 0으로 리셋
1. 연속 warning 3회로 error를 발송한 직후 카운트는 0으로 리셋
1. 즉시 error(2배 초과) 발생 시에도 연속 카운트는 0으로 리셋
1. 연속 warning error 요약 기간은 "첫 warning 시각 ~ 현재 시각"

## 상태 저장 설계

cron 1회성 실행 환경에서는 프로세스 메모리가 유지되지 않으므로 상태 파일(JSON)을 사용합니다.

- 기본 경로: $XDG_STATE_HOME/ntp_monitor/state.json
- XDG_STATE_HOME 미설정 시: ~/.local/state/ntp_monitor/state.json
- 설정으로 경로 오버라이드 가능: state.state_file_path

저장 항목:

- consecutive_warnings
- first_warning_ts
- last_warning_ts
- warning_jitters (최근 경고 지터 히스토리)

## 구현 포인트

1. 설정 확장

- monitoring.consecutive_warning_threshold (기본 3)
- monitoring.critical_jitter_multiplier (기본 2.0)
- state.state_file_path (선택)

1. 규칙 처리 순서

- jitter 수집 성공 후 warning 판단
- warning이면 기존 warning 로그 유지
- jitter >= threshold * multiplier 면 즉시 error 로그 발송 후 상태 리셋
- 그렇지 않으면 연속 warning 카운트 누적
- 연속 카운트 >= threshold이면 요약 error 로그 발송 후 상태 리셋
- 정상값이면 상태 리셋

1. 요약 error 로그

- 연속 횟수
- 기간(첫 warning ~ 마지막 warning)
- 임계치
- 최근 지터 min/max/latest

## 예시 로그

연속 warning 3회로 error 발송:

- ERROR NTP 지터 경고 연속 3회 발생으로 에러 발송 (기간: 2026-05-29 10:00:00 ~ 2026-05-29 10:10:00, 임계치: 1.00초, 최근 지터(min/max/latest): 1.10/1.40/1.40초)

2배 초과 즉시 error 발송:

- ERROR NTP 지터 임계치 2.0x 초과로 즉시 에러 발송 (현재: 2.20초, 임계치: 1.00초, 기준: 2.00초, 시각: 2026-05-29 10:05:00)

## 검증 시나리오

1. warning 1~2회 연속: warning만 발생, error 없음
1. warning 3회 연속: error 1회 발생 후 카운트 리셋
1. 2배 초과 1회: 즉시 error 발생
1. 정상값 발생: 연속 카운트 리셋
1. 상태 파일 부재/손상: 프로세스 중단 없이 기본 상태 복구
1. uv run 과 cron 래퍼 실행에서 동일 동작

## 운영 주의사항

1. state 파일 경로의 디렉토리 쓰기 권한이 필요합니다.
1. 상태 파일이 손상되면 warning 로그 후 기본 상태로 복구됩니다.
1. error 로그는 메일 발송 트리거이므로 임계치와 배수는 운영 정책에 맞게 조정하세요.
