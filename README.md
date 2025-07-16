# NTP Monitor

NTP 지터(Jitter) 모니터링 프로그램

## 개요

이 프로그램은 시스템의 NTP(Network Time Protocol) 지터 값을 모니터링하고, 임계치를 초과할 경우 시스템 로그에 경고를 기록하는 도구입니다. DietPi 및 다양한 Linux 시스템에서 동작하도록 설계되었습니다.

## 주요 기능

- **NTP 지터 모니터링**: `timedatectl show-timesync` 명령을 통해 실시간 지터 값 측정
- **다양한 단위 지원**: 초(s), 밀리초(ms), 마이크로초(μs) 단위 자동 인식 및 변환
- **설정 파일 지원**: `~/.ntp_monitor.conf` (사용자) 및 `/etc/ntp_monitor.conf` (시스템) 우선순위 기반 설정
- **유연한 임계치 설정**: 설정 파일을 통한 지터 임계치 조정 가능
- **시스템 로그 연동**: syslog를 통한 로그 기록 (로컬 syslog 또는 콘솔 출력)
- **크로스 플랫폼**: Linux (`/dev/log`), macOS/네트워크 (`localhost:514`) 환경 지원
- **디버그 모드**: 설정 파일 로드 상태 및 상세 정보 출력
- **오류 처리**: 안정적인 예외 처리 및 타임아웃 관리

## 요구사항

- Python 3.8 이상
- Linux 시스템 (systemd의 timedatectl 지원)
- NTP 서비스 실행 중

## 설치

### Rye 사용 (권장)

```bash
# 프로젝트 클론
git clone https://github.com/lum7671/ntp_monitor.git
cd ntp_monitor

# 의존성 설치
rye sync
```

### 직접 설치

```bash
# 프로젝트 클론
git clone https://github.com/lum7671/ntp_monitor.git
cd ntp_monitor

# 패키지 설치
pip install -e .
```

## 사용법

### 명령줄 실행

```bash
# Rye 환경에서 실행
rye run python -m ntp_monitor.main

# 직접 실행
python src/ntp_monitor/main.py

# 설치된 패키지로 실행 (pyproject.toml 스크립트 엔트리 사용)
ntp-monitor
```

### 정기 실행 (Cron)

시스템에서 정기적으로 모니터링하려면 cron에 등록하세요:

```bash
# crontab 편집
crontab -e

# 5분마다 실행 (예시)
*/5 * * * * /path/to/python /path/to/ntp_monitor/src/ntp_monitor/main.py
```

## 로그 출력 예시

### 정상 상태

```text
ntp_monitor: INFO NTP 상태 양호, 지터: 0.05초
```

### 임계치 초과

```text
ntp_monitor: WARNING NTP 지터 임계치 초과: 2.15초 (알림 전송됨)
```

### 오류 상황

```text
ntp_monitor: WARNING NTP 지터 값을 가져올 수 없습니다. NTP 서비스 상태를 확인하세요.
ntp_monitor: ERROR NTP 모니터링 중 오류 발생: [오류 내용]
```

### 디버그 모드

```text
ntp_monitor: INFO 설정 파일 로드됨: /home/user/.ntp_monitor.conf
ntp_monitor: INFO 지터 임계치: 1.5초
ntp_monitor: INFO NTP 상태 양호, 지터: 0.05초
```

## 설정

### 설정 파일

NTP Monitor는 다음 위치의 설정 파일을 우선순위에 따라 읽습니다:

1. `~/.ntp_monitor.conf` (사용자 설정, 우선순위 높음)
2. `/etc/ntp_monitor.conf` (시스템 설정)

#### 설정 파일의 장점

- **유연한 임계치 조정**: 코드 수정 없이 지터 임계치 변경
- **환경별 설정**: 개발/운영 환경에 맞는 다른 설정 적용
- **로그 레벨 제어**: DEBUG, INFO, WARNING, ERROR, CRITICAL 중 선택
- **플랫폼 적응**: Linux, macOS 등 환경에 맞는 syslog 설정
- **사용자별 커스터마이징**: 시스템 관리자와 사용자별 독립적 설정

#### 설정 파일 설치

```bash
# 설정 파일 자동 설치
./install_config.sh

# 시스템 전역 설정까지 설치 (root 권한 필요)
sudo ./install_config.sh
```

#### 수동 설정

```bash
# 사용자 설정 파일 생성
cp ntp_monitor.conf.example ~/.ntp_monitor.conf

# 시스템 설정 파일 생성 (root 권한 필요)
sudo cp ntp_monitor.conf.example /etc/ntp_monitor.conf
```

#### 설정 옵션

```ini
[monitoring]
# NTP 지터 임계치 (초 단위)
jitter_threshold = 2.0

# 디버그 모드 (true/false)
debug_mode = false

# 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
log_level = INFO

[logging]
# Syslog 주소 (Linux: /dev/log, 네트워크: localhost:514)
syslog_address = /dev/log
```

### 임계치 변경 (레거시)

코드에서 직접 변경하려면 `main.py`의 다음 부분을 수정하세요:

```python
if jitter > config['jitter_threshold']:  # 설정 파일에서 읽어옴
```

### 로그 설정

- **기본**: `/dev/log` (Linux syslog)
- **대체**: `localhost:514` (UDP syslog)
- **폴백**: 콘솔 출력
- **설정 가능**: 설정 파일의 `syslog_address`에서 변경 가능

### 디버그 기능

설정 파일에서 `debug_mode = true`로 설정하면:

- 로드된 설정 파일 정보 출력
- 현재 임계치 설정값 출력
- 더 상세한 로그 정보 제공

## 기술적 세부사항

### 설정 시스템

- **우선순위 기반 로딩**: `configparser.ConfigParser.read()`로 여러 파일 순차 읽기
- **안전한 폴백**: 모든 설정값에 기본값 제공
- **동적 로그 레벨**: 실행 시점에 로그 레벨 적용
- **플랫폼 감지**: 자동 syslog 주소 폴백 처리

### 지터 값 추출

프로그램은 다음 패턴들을 순서대로 시도하여 지터 값을 추출합니다:

1. `Jitter=X.XXs` (초 단위)
2. `Jitter=X.XXms` (밀리초 단위)
3. `Jitter=X.XXus` (마이크로초 단위)
4. `Jitter=X.XX` (단위 없음, 초로 가정)
5. 소문자 변형들

### 오류 처리

- 10초 타임아웃으로 명령 실행
- subprocess 오류 안전 처리
- 예외 상황에서도 프로그램 중단 없음

## 개발 환경

이 프로젝트는 [Rye](https://rye-up.com/)로 관리됩니다:

- **빌드 시스템**: Hatchling
- **패키지 구조**: src-layout
- **코딩 스타일**: 2-space 들여쓰기
- **설정 관리**: INI 형식 설정 파일 (`configparser` 사용)
- **크로스 플랫폼**: Linux, macOS 지원

### 프로젝트 구조

```text
ntp_monitor/
├── src/ntp_monitor/
│   ├── __init__.py
│   └── main.py              # 메인 모니터링 로직
├── ntp_monitor.conf.example # 설정 파일 템플릿
├── install_config.sh        # 설정 파일 설치 스크립트
├── pyproject.toml          # Rye 프로젝트 설정
└── README.md               # 프로젝트 문서
```

## 라이선스

이 프로젝트의 라이선스는 [LICENSE](LICENSE) 파일을 참조하세요.

## 기여

이슈 리포트나 풀 리퀘스트는 언제든 환영합니다.

.eol.
