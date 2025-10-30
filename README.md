# 이 `README.md`의 특수성
> Github 원격저장소의 README.md 파일은 일반적으로 해당 원격저장소(=프로젝트)에 대한 설명을 제공합니다.      
> 그러나 여러분이 읽고 계시는 이 README.md는 
- 개발자가 AI agent에게 이 프로젝트에 관련된 스크립트의 자동생성을 요청할 때, AI agent가 참고해야할 지침을 제공할 목적을 겸하도록 작성되었습니다.   
> 그래서, 프로젝트 폴더의 `.github/copilot-instructions.md`로부터 `README.md`로 심볼릭 링크를 구성하였는데, 이는 `README.md` 파일이 copilot의 지침으로 인식되도록 하기 위함입니다.   
> 이 문서는 때로는 AI agent의 지침으로 최적화하였기 때문에 일반적인 독자에게는 친화적이지 안을 수 있음을 참고하시길 바랍니다.   
> 이 README.md 문서에서는 비록 같은 내용이지만 두 가지 링크가 동시에 제공됩니다.
> 하나는 AI agent를 위한 로컬참조로써 로컬 저장소의 Wiki 문서가 링크되어 있습니다.
- 로컬참조는 개발단계에서 AI agent가 접근할 수 있도록 하기 위함이며 README.md 파일이 원격저장소에 푸시된 이후에는 아쉽게도 이 링크는 작동하지 않습니다.
> 다른 하나는 사용자(=독자)를 위한 원격참조로써 원격 저장소의 Wiki 문서가 링크되어 있습니다.
 - 원격참조는 여러분이 실제로 이 README.md 문서를 읽고 계시는 원격저장소에서 작동하므로 독자 여러분은 항상 원격참조를 사용하셔야 합니다.     
  
# 프로젝트 목적
> RPython 연구회에서 만든 여러가지 프로젝트들은 때로는 데이터베이스 등 공통적인 인프라성 서비스에 해당하는 것들이 필요할 수 있습니다.   
> 이 프로젝트는 이러한 서비스를 오픈소스를 이용하여 제공하는 플랫폼을 구축하고 관리함을 목적으로 합니다.

# 프로젝트 개요
> 프로젝트의 개요는 아래의 링크로 연결된 Wiki 문서를 참고하시길 바랍니다.      
- AI Agent를 위한 로컬참조: [Project-Overview](wiki/Project-Overview.md)   
- 사용자를 위한 원격참조: [Project Overview](https://github.com/RPythonStudy/rpy-quarto-template/wiki/Project-Overview)



# 공통으로 구현된 설정/기능
> 저자는 RPython 연구회용 프로젝트를 만들 때마다 rpy-quarto-template 원격저장소를 template로 사용하여 파생 프로젝트를 생성합니다.   
> Template를 통해 이미 구현된 공통 설정 및 기능은 아래와 같습니다.

## Python Import Path 설정
> {PROJECT_ROOT}/src 폴더를 기준폴더로 설정하여 import path 설정을 자동화하는 기능이 구현되어 있습니다.   
> 보다 구체적인 설명은 아래의 링크를 참고하시길 바랍니다.
- 로컬참조: [Python-Import-Path-Reference](wiki/Python-Import-Path-Reference(파이썬-임포트-경로-설정).md)
- 원격참조: [Python Import Path Reference](https://github.com/RPythonStudy/rpy-quarto-template/wiki/Python-Import-Path-Reference(파이썬-임포트-경로-설정))


## Python 가상환경
> 파이썬을 사용하는 프로젝트의 경우 가상환경을 생성한다고 전제하였습니다.   
> Requirements.txt로 패키지를 설치하시면 됩니다.   
> 가상화환경과 관련된 자동화 기능이 구현되어 있습니다. 


## Logging in R
- `src/R/logger.R` 사용
- .env파일로부터 PROJECT_NAME, LOG_LEVEL, LOG_PATH 로딩
- 함수: log_debug, log_info, log_warn, log_error
- log_fatal은 파이썬과 함수명을 통일하기 위해 log_critical로 래핑
- 보다 구체적인 예시는 아래 참조
- 로컬참조: [R-Logging-Reference](wiki/R-Logging-Reference.md)
- 원격참조: [R Logging Reference](https://github.com/RPythonStudy/rpy-quarto-template/wiki/R-Logging-Reference)
- Home참조: [Wiki Home](https://github.com/RPythonStudy/rpy-quarto-template/wiki/Home)



## Logging in Python 
- 로깅을 구현한 파일 위치: src/common/logger.py
- syspath에 src를 추가했으므로 `from common.logger import log_info`와 같이 import
- .env파일로부터 PROJECT_NAME, LOG_LEVEL, LOG_PATH 로딩
- config/logging.yml 파일로부터 로그포맷과 같은 복잡한 정책 관리
- 개인정보호 logging framework를 차용해 왔기 때문에 정책상 logs 폴더 직접생성해야 함 (단 설치 자동화 스크립트에서는 자동 생성구현됨). 폴더의 위치에 따라서는 권한문제 발생 가능
- 보다 구체적인 예시는 아래 참조
- 로컬참조: [Python-Logging-Reference](wiki/Python-Logging-Reference.md)
- 원격참조: [Python-Logging-Reference](https://github.com/RPythonStudy/rpy-quarto-template/wiki/Python-Logging-Reference)
- Home참조: [Wiki Home](https://github.com/RPythonStudy/rpy-quarto-template/wiki/Home)


## 사용자요청에 따른 AI agent의 스크립트 제안 시 참고해야할 지침
- 극단적으로 간결·직관·디버그 친화적 코드를 우선 제안
- Windows/Linux/macOS 간 경로 차이와 권한 이슈를 **사전 고지**하고, 필요 시 대체 경로 예시를 함께 제안
- 에러 메시지(예: 환경변수 치환 실패, 권한 오류)를 기반으로 **수정 가이드라인**까지 함께 제안

