import subprocess
import re
import logging
import logging.handlers
import sys
import configparser
import os
import socket
from typing import Optional, Dict, Any, List, Tuple, Union

# SyslogHandler: 로컬 syslog(기본 UDP 514 포트)에 전송
SYSLOG_ADDRESS = '/dev/log'  # 대부분의 Linux에서 지원, DietPi 호환

# 설정 파일 경로 (우선순위: /etc < HOME < 현재 디렉토리)
# ConfigParser는 나중에 읽은 파일 값이 우선 적용됩니다.
CONFIG_PATHS = [
  '/etc/ntp_monitor.conf',                     # 시스템 설정 파일
  os.path.expanduser('~/.ntp_monitor.conf'),   # 사용자 설정 파일
  '.ntp_monitor.conf',                         # 현재 디렉토리 (개발용)
]

SyslogAddress = Union[str, Tuple[str, int]]

def load_config() -> Dict[str, Any]:
  """
  설정 파일을 로드합니다.
  우선순위: /etc < ~/.ntp_monitor.conf < ./.ntp_monitor.conf
  
  Returns:
    Dict[str, Any]: 설정 값들
  """
  config = configparser.ConfigParser()
  
  # 설정 파일들을 우선순위에 따라 읽기
  config_files_read = config.read(CONFIG_PATHS)
  
  return {
    'jitter_threshold': config.getfloat('monitoring', 'jitter_threshold', fallback=2.0),
    'debug_mode': config.getboolean('monitoring', 'debug_mode', fallback=False),
    'log_level': config.get('monitoring', 'log_level', fallback='INFO'),
    'syslog_address': config.get('logging', 'syslog_address', fallback=SYSLOG_ADDRESS),
    'config_files_read': config_files_read  # 어떤 설정 파일이 읽혔는지 정보
  }

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
  
  # 디버그 모드에서 설정 정보 출력
  if config['debug_mode']:
    if config['config_files_read']:
      logger.info(f"설정 파일 로드됨: {', '.join(config['config_files_read'])}")
    else:
      logger.info("설정 파일을 찾을 수 없음, 기본값 사용")
    logger.info(f"지터 임계치: {config['jitter_threshold']}초")
  
  try:
    jitter = get_jitter()
    
    if jitter is None:
      logger.warning("NTP 지터 값을 가져올 수 없습니다. NTP 서비스 상태를 확인하세요.")
      return
    
    if jitter > config['jitter_threshold']:
      logger.warning(f"NTP 지터 임계치 초과: {jitter:.2f}초 (임계치: {config['jitter_threshold']}초)")
    else:
      logger.info(f"NTP 상태 양호, 지터: {jitter:.2f}초")
      
  except Exception as e:
    logger.error(f"NTP 모니터링 중 오류 발생: {e}")
    
if __name__ == "__main__":
  main()
