import subprocess
import re
import logging
import logging.handlers
import sys
import configparser
import os
import socket
import json
import tempfile
import time
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple, Union

# SyslogHandler: 로컬 syslog(기본 UDP 514 포트)에 전송
SYSLOG_ADDRESS = '/dev/log'  # 대부분의 Linux에서 지원, DietPi 호환

def get_default_user_config_path() -> str:
  """XDG 표준 사용자 설정 파일 경로를 반환합니다."""
  xdg_config_home = os.getenv('XDG_CONFIG_HOME')
  if xdg_config_home:
    return os.path.join(xdg_config_home, 'ntp_monitor', 'config.ini')
  return os.path.expanduser('~/.config/ntp_monitor/config.ini')

def get_config_paths() -> List[str]:
  """
  설정 파일 탐색 경로를 반환합니다.
  우선순위: /etc < ~/.ntp_monitor.conf < ~/.config/ntp_monitor/config.ini < ./.ntp_monitor.conf
  """
  return [
    '/etc/ntp_monitor.conf',                     # 시스템 설정 파일
    os.path.expanduser('~/.ntp_monitor.conf'),   # 레거시 사용자 설정 파일
    get_default_user_config_path(),              # XDG 사용자 설정 파일
    '.ntp_monitor.conf',                         # 현재 디렉토리 (개발용)
  ]

SyslogAddress = Union[str, Tuple[str, int]]

DEFAULT_CONSECUTIVE_WARNING_THRESHOLD = 3
DEFAULT_CRITICAL_JITTER_MULTIPLIER = 2.0

DEFAULT_STATE = {
  'consecutive_warnings': 0,
  'first_warning_ts': None,
  'last_warning_ts': None,
  'warning_jitters': [],
}

def load_config() -> Dict[str, Any]:
  """
  설정 파일을 로드합니다.
  우선순위: /etc < ~/.ntp_monitor.conf < ~/.config/ntp_monitor/config.ini < ./.ntp_monitor.conf
  
  Returns:
    Dict[str, Any]: 설정 값들
  """
  config = configparser.ConfigParser()
  
  # 설정 파일들을 우선순위에 따라 읽기
  config_files_read = config.read(get_config_paths())
  
  return {
    'jitter_threshold': config.getfloat('monitoring', 'jitter_threshold', fallback=2.0),
    'consecutive_warning_threshold': config.getint(
      'monitoring',
      'consecutive_warning_threshold',
      fallback=DEFAULT_CONSECUTIVE_WARNING_THRESHOLD,
    ),
    'critical_jitter_multiplier': config.getfloat(
      'monitoring',
      'critical_jitter_multiplier',
      fallback=DEFAULT_CRITICAL_JITTER_MULTIPLIER,
    ),
    'debug_mode': config.getboolean('monitoring', 'debug_mode', fallback=False),
    'log_level': config.get('monitoring', 'log_level', fallback='INFO'),
    'syslog_address': config.get('logging', 'syslog_address', fallback=SYSLOG_ADDRESS),
    'state_file_path': config.get('state', 'state_file_path', fallback='').strip(),
    'config_files_read': config_files_read  # 어떤 설정 파일이 읽혔는지 정보
  }

def get_default_state_file_path() -> str:
  """기본 상태 파일 경로를 반환합니다."""
  xdg_state_home = os.getenv('XDG_STATE_HOME')
  if xdg_state_home:
    return os.path.join(xdg_state_home, 'ntp_monitor', 'state.json')
  return os.path.expanduser('~/.local/state/ntp_monitor/state.json')

def get_state_file_path(config: Dict[str, Any]) -> str:
  """설정값 또는 기본 경로로 상태 파일 경로를 결정합니다."""
  configured_path = str(config.get('state_file_path', '')).strip()
  if configured_path:
    return os.path.expanduser(configured_path)
  return get_default_state_file_path()

def _normalize_state(raw_state: Dict[str, Any]) -> Dict[str, Any]:
  """상태 파일 값을 내부 기본 스키마로 정규화합니다."""
  normalized = dict(DEFAULT_STATE)
  normalized['consecutive_warnings'] = int(raw_state.get('consecutive_warnings', 0))
  normalized['first_warning_ts'] = raw_state.get('first_warning_ts')
  normalized['last_warning_ts'] = raw_state.get('last_warning_ts')

  warning_jitters = raw_state.get('warning_jitters', [])
  if isinstance(warning_jitters, list):
    normalized['warning_jitters'] = [float(j) for j in warning_jitters if isinstance(j, (int, float))]
  else:
    normalized['warning_jitters'] = []

  if normalized['consecutive_warnings'] <= 0:
    reset_warning_state(normalized)

  return normalized

def load_state(state_file_path: str, logger: logging.Logger) -> Dict[str, Any]:
  """상태 파일을 읽고 문제가 있으면 기본 상태를 반환합니다."""
  if not os.path.exists(state_file_path):
    return dict(DEFAULT_STATE)

  try:
    with open(state_file_path, 'r', encoding='utf-8') as file_obj:
      return _normalize_state(json.load(file_obj))
  except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
    logger.warning(f"상태 파일 읽기 실패로 기본값을 사용합니다: {error}")
    return dict(DEFAULT_STATE)

def save_state(state_file_path: str, state: Dict[str, Any], logger: logging.Logger) -> None:
  """상태 파일을 원자적으로 저장합니다."""
  try:
    state_dir = os.path.dirname(state_file_path)
    if state_dir:
      os.makedirs(state_dir, exist_ok=True)

    with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=state_dir or None, delete=False) as temp_file:
      json.dump(state, temp_file, ensure_ascii=False, sort_keys=True)
      temp_file.flush()
      os.fsync(temp_file.fileno())
      temp_path = temp_file.name

    os.replace(temp_path, state_file_path)
  except OSError as error:
    logger.warning(f"상태 파일 저장 실패: {error}")

def reset_warning_state(state: Dict[str, Any]) -> None:
  """연속 경고 상태를 초기화합니다."""
  state['consecutive_warnings'] = 0
  state['first_warning_ts'] = None
  state['last_warning_ts'] = None
  state['warning_jitters'] = []

def update_warning_state(state: Dict[str, Any], jitter: float, now_ts: int) -> None:
  """임계값 초과 시 연속 경고 상태를 갱신합니다."""
  if state['consecutive_warnings'] == 0:
    state['first_warning_ts'] = now_ts

  state['consecutive_warnings'] += 1
  state['last_warning_ts'] = now_ts

  warning_jitters = state.get('warning_jitters', [])
  warning_jitters.append(round(jitter, 6))
  state['warning_jitters'] = warning_jitters[-20:]

def format_ts(unix_ts: Optional[int]) -> str:
  """유닉스 타임스탬프를 읽기 쉬운 로컬 시각 문자열로 변환합니다."""
  if not unix_ts:
    return '-'
  return datetime.fromtimestamp(unix_ts).strftime('%Y-%m-%d %H:%M:%S')

def log_consecutive_warning_error(logger: logging.Logger, state: Dict[str, Any], threshold: float) -> None:
  """연속 경고 임계 도달 시 요약 error 로그를 남깁니다."""
  warning_jitters = state.get('warning_jitters', [])
  if warning_jitters:
    min_jitter = min(warning_jitters)
    max_jitter = max(warning_jitters)
    latest_jitter = warning_jitters[-1]
    jitter_summary = f"최근 지터(min/max/latest): {min_jitter:.2f}/{max_jitter:.2f}/{latest_jitter:.2f}초"
  else:
    jitter_summary = '최근 지터 정보 없음'

  logger.error(
    "NTP 지터 경고 연속 %d회 발생으로 에러 발송 "
    "(기간: %s ~ %s, 임계치: %.2f초, %s)",
    state.get('consecutive_warnings', 0),
    format_ts(state.get('first_warning_ts')),
    format_ts(state.get('last_warning_ts')),
    threshold,
    jitter_summary,
  )

def log_critical_jitter_error(logger: logging.Logger, jitter: float, threshold: float, multiplier: float) -> None:
  """임계값 배수 초과 시 즉시 error 로그를 남깁니다."""
  logger.error(
    "NTP 지터 임계치 %.1fx 초과로 즉시 에러 발송 "
    "(현재: %.2f초, 임계치: %.2f초, 기준: %.2f초, 시각: %s)",
    multiplier,
    jitter,
    threshold,
    threshold * multiplier,
    format_ts(int(time.time())),
  )

def parse_syslog_address(raw_address: str) -> SyslogAddress:
  """
  syslog 주소 문자열을 파싱합니다.

  - /dev/log 같은 절대 경로는 unix socket 경로로 사용
  - host:port 형식은 (host, port) 튜플로 변환
  """
  value = raw_address.strip()

  # unix socket 경로는 그대로 사용
  if '/' in value and not (':' in value and value.count(':') == 1 and value.rsplit(':', 1)[1].isdigit()):
    return value

  if ':' in value:
    host, port_text = value.rsplit(':', 1)
    if host and port_text.isdigit():
      return (host, int(port_text))

  return value

def build_syslog_candidates(configured_address: SyslogAddress) -> List[SyslogAddress]:
  """설정값 우선으로 syslog 후보 주소 목록을 구성합니다."""
  candidates: List[SyslogAddress] = [
    configured_address,
    '/dev/log',
    '/run/systemd/journal/dev-log',
    ('localhost', 514),
  ]

  unique_candidates: List[SyslogAddress] = []
  for candidate in candidates:
    if candidate not in unique_candidates:
      unique_candidates.append(candidate)

  return unique_candidates

def create_syslog_handler(address: SyslogAddress) -> Optional[logging.Handler]:
  """
  주소 유형에 맞춰 SysLogHandler를 생성합니다.
  유효하지 않은 unix socket 경로는 생성하지 않습니다.
  """
  if isinstance(address, str):
    if not address.startswith('/'):
      return None
    if not os.path.exists(address):
      return None
    return logging.handlers.SysLogHandler(address=address)

  return logging.handlers.SysLogHandler(address=address, socktype=socket.SOCK_DGRAM)

def get_jitter() -> Optional[float]:
  """
  NTP 지터 값을 timedatectl에서 추출합니다.
  
  Returns:
    float: 지터 값 (초 단위)
    None: 지터 값을 찾을 수 없는 경우
  """
  try:
    result = subprocess.run(['timedatectl', 'show-timesync'],
                            capture_output=True, text=True, timeout=10)
    
    if result.returncode != 0:
      return None
      
    # 여러 패턴 시도 (단위 변환 포함)
    patterns = [
      (r'Jitter=([\d\.]+)s', 1),        # 초 단위
      (r'Jitter=([\d\.]+)ms', 0.001),   # 밀리초 단위
      (r'Jitter=([\d\.]+)us', 0.000001), # 마이크로초 단위
      (r'Jitter=([\d\.]+)', 1),         # 단위 없음 (기본 초)
      (r'jitter=([\d\.]+)s', 1),        # 소문자
      (r'jitter=([\d\.]+)', 1),         # 소문자, 단위 없음
    ]
    
    for pattern, multiplier in patterns:
      match = re.search(pattern, result.stdout, re.IGNORECASE)
      if match:
        return float(match.group(1)) * multiplier
        
    return None
    
  except subprocess.TimeoutExpired:
    return None
  except subprocess.CalledProcessError:
    return None
  except Exception:
    return None

def setup_logger(config: Dict[str, Any]) -> logging.Logger:
  """로거 설정"""
  logger = logging.getLogger('ntp_monitor')

  # 로깅 핸들러 내부 예외 traceback이 stderr로 노출되지 않도록 방지합니다.
  logging.raiseExceptions = False
  
  # 로그 레벨 설정
  log_level = getattr(logging, config['log_level'].upper(), logging.INFO)
  logger.setLevel(log_level)
  
  # 기존 핸들러 제거
  for handler in logger.handlers[:]:
    logger.removeHandler(handler)
  
  syslog_address = parse_syslog_address(str(config['syslog_address']))

  selected_handler: Optional[logging.Handler] = None
  selected_target = 'stdout'

  for candidate in build_syslog_candidates(syslog_address):
    try:
      handler = create_syslog_handler(candidate)
      if handler is None:
        continue
      selected_handler = handler
      selected_target = str(candidate)
      break
    except (OSError, ValueError):
      continue

  if selected_handler is None:
    selected_handler = logging.StreamHandler(sys.stdout)
  
  formatter = logging.Formatter('%(name)s: %(levelname)s %(message)s')
  selected_handler.setFormatter(formatter)
  logger.addHandler(selected_handler)

  if config.get('debug_mode', False):
    logger.info(f"로깅 출력 대상: {selected_target}")
  
  return logger

def main():
  config = load_config()
  logger = setup_logger(config)
  state_file_path = get_state_file_path(config)
  state = load_state(state_file_path, logger)

  consecutive_warning_threshold = max(1, int(config['consecutive_warning_threshold']))
  critical_jitter_multiplier = max(1.0, float(config['critical_jitter_multiplier']))
  
  # 디버그 모드에서 설정 정보 출력
  if config['debug_mode']:
    if config['config_files_read']:
      logger.info(f"설정 파일 로드됨: {', '.join(config['config_files_read'])}")
    else:
      logger.info("설정 파일을 찾을 수 없음, 기본값 사용")
    logger.info(f"지터 임계치: {config['jitter_threshold']}초")
    logger.info(f"연속 경고 에러 기준: {consecutive_warning_threshold}회")
    logger.info(f"즉시 에러 기준 배수: {critical_jitter_multiplier:.1f}x")
    logger.info(f"상태 파일 경로: {state_file_path}")
  
  try:
    jitter = get_jitter()
    
    if jitter is None:
      logger.warning("NTP 지터 값을 가져올 수 없습니다. NTP 서비스 상태를 확인하세요.")
      return

    if jitter > config['jitter_threshold']:
      logger.warning(f"NTP 지터 임계치 초과: {jitter:.2f}초 (임계치: {config['jitter_threshold']}초)")

      # 임계치 2배 이상이면 즉시 error 로그 발송
      if jitter >= (config['jitter_threshold'] * critical_jitter_multiplier):
        log_critical_jitter_error(logger, jitter, config['jitter_threshold'], critical_jitter_multiplier)
        reset_warning_state(state)
        save_state(state_file_path, state, logger)
        return

      now_ts = int(time.time())
      update_warning_state(state, jitter, now_ts)

      if state['consecutive_warnings'] >= consecutive_warning_threshold:
        log_consecutive_warning_error(logger, state, config['jitter_threshold'])
        reset_warning_state(state)

    else:
      logger.info(f"NTP 상태 양호, 지터: {jitter:.2f}초")
      # 정상값이 나오면 연속 경고 상태를 초기화
      reset_warning_state(state)

    save_state(state_file_path, state, logger)
      
  except Exception as e:
    logger.error(f"NTP 모니터링 중 오류 발생: {e}")
    
if __name__ == "__main__":
  main()
