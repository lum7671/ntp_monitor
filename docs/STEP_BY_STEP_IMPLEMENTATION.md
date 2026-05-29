# 단계별 개발 문서 (Step by Step)

이 문서는 1차 범위(에러 수정 + 최소 리팩토링)를 기준으로 실제 작업 순서대로 작성되었습니다.

## Step 0. 작업 준비

목표: 변경 이력/검증 증적이 남도록 준비

- 작업 전 요구사항 범위 확정(1차: 에러 수정 + 최소 리팩토링)
- 변경 파일 목록 추적
- 검증 결과 문서 위치 확정: docs/VALIDATION_RESULTS.md

완료 기준

- 작업 범위와 산출물 위치가 합의되어 있음

## Step 1. 기준선 확보

목표: 현재 문제와 재현 조건을 명확히 고정

- traceback 로그를 보관
- 실행 환경(DietPi, Python 3.14+) 기록
- 사용한 설정 파일 경로 기록

완료 기준

- 문제 재현 로그와 환경 정보가 문서로 정리되어 있음

## Step 2. 원인 분석

목표: 문제를 코드 레벨 원인으로 분해

- syslog_address 형식(host:port vs unix socket) 점검
- /dev/log 존재 여부 점검
- SysLogHandler fallback 경로 점검

완료 기준

- 원인 목록과 대응 전략이 정의되어 있음

## Step 3. 코드 수정 (1차)

목표: 로깅 에러 재발 방지

- syslog 주소 파싱 함수 추가
- 유효한 주소 후보를 순차 시도
- 실패 시 stdout으로 안전 fallback
- logging 내부 traceback 억제

완료 기준

- Logging error traceback 미발생
- debug_mode에서 로깅 대상 확인 가능

## Step 4. 최소 리팩토링

목표: 유지보수성 개선

- 로깅 관련 로직을 보조 함수로 분리
- 기존 비즈니스 로직(get_jitter, threshold 비교)은 동작 변경 없이 유지

완료 기준

- 함수 책임이 명확해지고 코드 가독성 향상

## Step 5. 문서 정합화

목표: 코드와 문서의 동작 설명 일치

- 설정 우선순위 설명 보정
- syslog_address 사용 예시 보강
- Python 버전 요구사항 정합화

완료 기준

- README와 실제 동작이 일치

## Step 6. 검증

목표: 운영 관점 확인

검증 케이스

1. syslog_address = /dev/log, 소켓 존재
1. syslog_address = /dev/log, 소켓 미존재
1. syslog_address = localhost:514
1. syslog_address = 잘못된 문자열

완료 기준

- 어떤 케이스에서도 내부 logging traceback이 출력되지 않음
- 최소 하나의 출력 경로(syslog 또는 stdout)가 동작

검증 증적

- 실행 결과를 docs/VALIDATION_RESULTS.md에 기록
- 최소 항목: 테스트 일시, 실행 명령, 케이스별 통과/실패, 미검증 항목

## Step 7. 다음 단계(2차)

목표: 구조 개선 확장

- 파일 분리: config.py, logging.py, monitor.py
- 단위 테스트 추가
- cron 운영 가이드 강화(stderr 별도 보관)

완료 기준

- 리팩토링 브랜치에서 테스트 기반으로 안정적으로 확장 가능

## Step 8. 운영 반영 체크

목표: 실제 운영 반영 전 누락 방지

- README, 설정 예시, 코드 동작 정합성 재확인
- 크론 적용 시 stderr 보관 정책 확인
- 롤백 방법(이전 버전 재배포 또는 설정 복구) 기록

완료 기준

- 운영 적용/롤백 체크리스트가 문서화됨
