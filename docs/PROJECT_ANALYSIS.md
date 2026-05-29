# NTP Monitor 프로젝트 분석

## 1. 프로젝트 목적
NTP 지터 값을 주기적으로 점검하고, 임계치 초과 여부를 로그로 남기는 경량 모니터링 도구입니다.

## 2. 현재 구조
- src/ntp_monitor/main.py: 설정 로드, 로거 설정, 지터 조회, 임계치 비교를 모두 포함한 단일 파일
- ntp_monitor.conf.example: 기본 설정 템플릿
- scripts/run_ntp_monitor.sh: cron 실행용 래퍼
- install_config.sh: 설정 파일 배치 도우미

## 3. 실행 흐름
1. 설정 파일을 순서대로 읽음
2. 로깅 핸들러를 초기화
3. timedatectl show-timesync 실행
4. Jitter 값을 파싱하고 초 단위로 정규화
5. 임계치 비교 후 INFO/WARNING 로그 출력

## 4. 이번에 확인된 핵심 문제
### 4.1 Logging traceback 발생
- 증상: --- Logging error --- 와 함께 Bad file descriptor, No such file or directory 발생
- 원인 1: syslog_address 값이 localhost:514 문자열일 때 SysLogHandler가 unix socket 경로로 오해 가능
- 원인 2: /dev/log 같은 unix socket이 없는 환경에서 syslog 핸들러 생성/emit 시 내부 예외 반복

### 4.2 설정 우선순위 설명 불일치
- 문서 설명과 실제 ConfigParser 동작(나중에 읽은 값이 우선)이 맞지 않는 부분이 있었음

## 5. 1차 개선 목표
- 로깅 내부 traceback 제거
- syslog 주소 파싱 및 fallback 강화
- 설정 우선순위 설명과 실제 동작 정합화
- 대규모 파일 분리 없이 최소 리팩토링

## 6. 2차 리팩토링 후보
- config, logging, monitor 책임 분리
- 단위 테스트 추가(주소 파싱, fallback, jitter 파싱)
- timedatectl 의존 구간의 인터페이스 분리
