import subprocess
import re
import logging
import logging.handlers
import sys
import configparser
import os
from typing import Optional, Dict, Any

# SyslogHandler: 로컬 syslog(기본 UDP 514 포트)에 전송
SYSLOG_ADDRESS = '/dev/log'  # 대부분의 Linux에서 지원, DietPi 호환

# 설정 파일 경로 (우선순위: 현재 디렉토리 > HOME > /etc)
CONFIG_PATHS = [
  '.ntp_monitor.conf',                        # 현재 디렉토리 (개발용)
  os.path.expanduser('~/.ntp_monitor.conf'),  # 사용자 설정 파일
  '/etc/ntp_monitor.conf'                     # 시스템 설정 파일
]

def load_config() -> Dict[str, Any]:
  """
  설정 파일을 로드합니다.
  우선순위: ~/.ntp_monitor.conf > /etc/ntp_monitor.conf
  
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
  
  # 로그 레벨 설정
  log_level = getattr(logging, config['log_level'].upper(), logging.INFO)
  logger.setLevel(log_level)
  
  # 기존 핸들러 제거
  for handler in logger.handlers[:]:
    logger.removeHandler(handler)
  
  syslog_address = config['syslog_address']
  
  try:
    syslog_handler = logging.handlers.SysLogHandler(address=syslog_address)
  except Exception:
    # 일부 시스템에서는 /dev/log 대신 ('localhost', 514) 필요
    try:
      syslog_handler = logging.handlers.SysLogHandler(address=('localhost', 514))
    except Exception:
      # syslog 사용 불가 시 콘솔로 출력
      syslog_handler = logging.StreamHandler(sys.stdout)
  
  formatter = logging.Formatter('%(name)s: %(levelname)s %(message)s')
  syslog_handler.setFormatter(formatter)
  logger.addHandler(syslog_handler)
  
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
