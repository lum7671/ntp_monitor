# Logging 에러 수정 내역

## 배경
DietPi 환경에서 아래와 같은 내부 로깅 오류가 반복 발생했습니다.
- OSError: [Errno 9] Bad file descriptor
- FileNotFoundError: [Errno 2] No such file or directory

## 수정 파일
- src/ntp_monitor/main.py

## 변경 사항 요약
1. syslog_address 파싱 함수 추가
- host:port 문자열을 (host, port) 튜플로 변환
- unix socket 경로와 네트워크 주소를 구분

2. syslog 후보 주소 순차 시도 로직 추가
- 설정값
- /dev/log
- /run/systemd/journal/dev-log
- ('localhost', 514)
- 모두 실패하면 StreamHandler(stdout) 사용

3. 유효하지 않은 문자열 주소 방어
- 문자열 주소는 절대 경로 unix socket만 허용
- 파일이 없으면 해당 후보는 건너뜀

4. 내부 traceback 노출 방지
- logging.raiseExceptions = False 적용
- 개발/운영에서 핸들러 내부 예외가 stderr traceback으로 노출되지 않도록 처리

5. debug_mode에서 로깅 출력 대상 확인 가능
- 로깅 출력 대상(예: /dev/log, ('localhost', 514), stdout)을 로그로 남김

## 기대 효과
- syslog 소켓 부재 환경에서도 프로그램이 정상 동작
- host:port 설정을 안전하게 지원
- 기존처럼 로깅 예외 traceback이 콘솔을 오염시키지 않음

## 주의사항
- logging.raiseExceptions = False는 핸들러 내부 예외 traceback만 숨기며, 애플리케이션 예외 처리에는 영향이 없습니다.
- syslog daemon 자체가 비활성인 환경에서는 stdout fallback 로그를 사용합니다.
