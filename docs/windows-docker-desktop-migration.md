# WSL2 → Windows + Docker Desktop 마이그레이션 가이드

## 현재 프로젝트의 WSL2 → Windows 호환성 분석

### ✅ 호환 가능한 요소들
- Docker Compose 파일들 (완전 호환)
- Python 스크립트들 (Path 라이브러리 사용으로 크로스플랫폼 지원)
- 프로젝트 구조 (상대 경로 기반)
- 로깅 시스템 (이미 Windows 경로 지원 구현됨)

### ⚠️ 수정이 필요한 요소들

#### 1. **권한 관리 시스템**
```python
# 현재 (Linux/WSL2 전용)
sudo chown 100:100 /opt/ai4rm/vault/
sudo chmod 640 vault.key

# Windows 대응 필요
# Windows에서는 sudo/chown/chmod가 작동하지 않음
```

#### 2. **sudo 명령어 제거**
```python
# 현재 코드에서 많이 사용되는 패턴
subprocess.run(["sudo", "docker", "compose", "up", "-d"])

# Windows Docker Desktop용으로 변경 필요
subprocess.run(["docker", "compose", "up", "-d"])
```

#### 3. **경로 처리**
```python
# 현재 하드코딩된 Linux 경로들
"/opt/ai4rm/"
"/var/log/"
"/dev/log"  # syslog

# Windows 대응 경로로 변경 필요
"C:\\ProgramData\\ai4rm\\"
"%USERPROFILE%\\AppData\\Local\\ai4rm\\logs"
```

#### 4. **네트워크 및 파일시스템**
```python
# WSL2의 /mnt/c/ 패턴 
"/mnt/d/"  # USB 마운트 경로

# Windows의 드라이브 문자 패턴
"D:\\"
```

## 마이그레이션 전략

### 전략 1: **크로스플랫폼 지원 (권장)**

현재 프로젝트를 WSL2/Linux와 Windows 모두에서 작동하도록 개선:

```python
# config/platform.yml (새로 생성)
platforms:
  linux:
    base_path: "/opt/ai4rm"
    log_path: "/var/log/{PROJECT_NAME}"
    use_sudo: true
    docker_command: ["sudo", "docker"]
    
  windows:
    base_path: "C:\\ProgramData\\ai4rm"
    log_path: "%USERPROFILE%\\AppData\\Local\\{PROJECT_NAME}\\logs"
    use_sudo: false
    docker_command: ["docker"]
    
  wsl2:
    base_path: "/opt/ai4rm"
    log_path: "/var/log/{PROJECT_NAME}"
    use_sudo: true
    docker_command: ["sudo", "docker"]
```

#### 구현 예시:
```python
# src/ai4rm/core/platform_manager.py
import platform
import os
from pathlib import Path

class PlatformManager:
    def __init__(self):
        self.os_type = self._detect_platform()
        self.config = self._load_platform_config()
    
    def _detect_platform(self):
        system = platform.system().lower()
        if system == "linux":
            # WSL2 감지
            if os.path.exists("/proc/version"):
                with open("/proc/version", "r") as f:
                    if "microsoft" in f.read().lower():
                        return "wsl2"
            return "linux"
        elif system == "windows":
            return "windows"
        elif system == "darwin":
            return "macos"
        return "unknown"
    
    def get_docker_command(self):
        """플랫폼별 Docker 명령어 반환"""
        if self.os_type in ["linux", "wsl2"]:
            return ["sudo", "docker"]
        else:  # Windows, macOS
            return ["docker"]
    
    def get_base_path(self):
        """플랫폼별 기본 설치 경로 반환"""
        if self.os_type in ["linux", "wsl2"]:
            return Path("/opt/ai4rm")
        elif self.os_type == "windows":
            return Path("C:/ProgramData/ai4rm")
        else:
            return Path.home() / "ai4rm"
    
    def requires_sudo(self):
        """sudo 권한이 필요한지 확인"""
        return self.os_type in ["linux", "wsl2"]
```

### 전략 2: **Windows 전용 브랜치**

Windows 전용으로 별도 브랜치를 만들어 관리:

```bash
git checkout -b windows-docker-desktop
# Windows 전용 수정사항 적용
```

### 전략 3: **Docker Desktop 최적화**

Docker Desktop의 특성을 활용한 구조로 재설계:

```python
# Windows + Docker Desktop 최적화 구조
ai4rm-windows/
├── data/               # Docker Desktop의 볼륨 마운트
│   ├── postgres/
│   ├── vault/
│   └── elk/
├── config/
├── logs/
└── ai4rm-cli.py
```

## 구체적인 수정 사항

### 1. **Docker Compose 수정**
```yaml
# 현재 (Linux 경로)
volumes:
  - /opt/ai4rm/postgres/data:/var/lib/postgresql/data

# Windows 대응
volumes:
  - ${AI4RM_DATA_DIR:-C:/ProgramData/ai4rm}/postgres/data:/var/lib/postgresql/data
```

### 2. **권한 관리 수정**
```python
# 기존 Linux/WSL2용 코드
def set_permissions_linux(path, owner="1000:1000", mode="755"):
    subprocess.run(["sudo", "chown", owner, str(path)])
    subprocess.run(["sudo", "chmod", mode, str(path)])

# Windows 대응 코드 추가
def set_permissions_windows(path):
    # Windows에서는 Docker Desktop이 자동으로 권한 처리
    # 또는 PowerShell의 icacls 명령어 사용
    pass

def set_permissions(path, platform_manager):
    if platform_manager.requires_sudo():
        set_permissions_linux(path)
    else:
        set_permissions_windows(path)
```

### 3. **경로 처리 통합**
```python
# 현재 하드코딩
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = "/opt/ai4rm"

# 플랫폼 독립적으로 변경
class PathManager:
    def __init__(self, platform_manager):
        self.platform = platform_manager
        
    def get_install_path(self, service):
        base = self.platform.get_base_path()
        return base / service
        
    def get_data_path(self, service):
        return self.get_install_path(service) / "data"
        
    def get_config_path(self, service):
        return self.get_install_path(service) / "config"
```

## 권장 접근법

**크로스플랫폼 지원 (전략 1)을 권장**합니다:

### 이유:
1. **코드 중복 방지**: 하나의 코드베이스로 여러 플랫폼 지원
2. **유지보수 효율성**: 기능 추가 시 모든 플랫폼에 동시 적용
3. **사용자 편의성**: 환경에 관계없이 동일한 명령어 사용 가능

### 구현 우선순위:
1. **플랫폼 감지 시스템** 구현
2. **Docker 명령어 통합** (sudo 유무 자동 처리)  
3. **경로 관리 시스템** 통합
4. **권한 관리 시스템** 플랫폼별 분기
5. **설정 파일** 플랫폼별 기본값 제공

이렇게 구현하면 WSL2에서 개발하고 Windows로 클론해도 동일하게 작동하며, Docker Desktop과 완벽하게 연계됩니다.
