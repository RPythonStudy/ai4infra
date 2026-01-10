# Elastic Stack (ELK) Service Guide

> **서비스명**: `ai4infra-elasticsearch`, `ai4infra-kibana`, `ai4infra-logstash`, `ai4infra-filebeat`
> **역할**: 중앙 집중식 로그 수집, 저장, 분석 및 시각화
> **URL**: `http://kibana.ai4infra.internal` (Nginx Proxy)

## 1. Overview
`ai4infra` 프로젝트의 Observability를 담당하는 Elastic Stack(EFK)입니다.
모든 컨테이너와 애플리케이션 로그는 **Filebeat**를 통해 수집되고, **Logstash**를 거쳐 **Elasticsearch**에 저장되며, **Kibana**를 통해 시각화됩니다.

### Data Pipeline
`[Source: Container/App Logs]` → `[Filebeat]` → `(JSON Parsing)` → `[Logstash]` → `[Elasticsearch]` → `[Kibana]`

### Components
- **Elasticsearch**: 로그 데이터 원장 저장소 (NoSQL).
- **Kibana**: 대시보드 및 검색 UI.
- **Logstash**: 데이터 수신 및 전처리 (TCP 5044).
- **Filebeat**: 각 로그 소스(Docker, 파일)에서 데이터를 읽어 Logstash로 전송하는 경량 에이전트.

## 2. Architecture & Network
- **Gateway**: Nginx가 `kibana.ai4infra.internal` 요청을 `ai4infra-kibana:5601`로 프록시.
- **Internal**: 모든 컴포넌트는 `ai4infra` Docker 네트워크 내에서 서로 통신.
- **Security**: 현재 개발 단계에서는 xPack Security(로그인)가 비활성화되어 있습니다.

## 3. Configuration (`config/elk.yml`)
사용자는 `config/elk.yml`을 통해 주요 포트 및 리소스 설정을 변경할 수 있습니다.

```yaml
compose_vars:
  ES_MEM_LIMIT: "2g"
  ES_JAVA_OPTS: "-Xms1g -Xmx1g"
  LOGSTASH_PORT: "5044"
  # 호스트 로그 파일 수집 경로 (.env LOG_PATH 기준)
  LOG_PATH: "/var/log/ai4infra"
```

## 4. Prerequisites (System Setting)
**Elasticsearch 구동을 위한 필수 커널 설정**:
```bash
# 영구 적용 (/etc/sysctl.conf)
vm.max_map_count=262144

# 적용 확인
sysctl vm.max_map_count
```

## 5. Log Collection Strategy

### A. Docker Container Logs
- **방식**: Filebeat Autodiscover (`ai4infra-filebeat`)
- **대상**: `/var/lib/docker/containers/*/*.log`
- **특징**: 모든 컨테이너의 Standard Output(stdout/stderr)을 자동으로 수집.

### B. Application Logs (Python)
- **방식**: Filebeat Log Input
- **대상**: `${LOG_PATH}/*.log` (예: `/var/log/ai4infra/service.log`)
- **포맷**: JSON (Python `logger.py`가 JSON 포맷으로 기록)
- **설정**: `config/filebeat/filebeat.yml` 참조

## 6. Installation & Operation

### 설치
```bash
make install-elk
```
> **Note**: `elasticsearch`, `kibana`, `logstash`, `filebeat` 컨테이너가 순차적으로 실행됩니다. 설치 스크립트가 데이터 디렉토리 권한(`1000:0`)을 자동으로 `setup`합니다.

### 상태 확인
```bash
sudo docker ps | grep ai4infra
sudo docker logs -f ai4infra-logstash  # 로그 수신 확인
```

### Kibana 초기 설정
1. 브라우저 접속: `http://kibana.ai4infra.internal`
2. **Index Patterns** 메뉴 이동.
3. **Create index pattern** 클릭.
4. Name: `ai4infra-*` 입력 (Logstash가 데이터를 넣기 시작해야 나타남).
5. Timestamp field: `@timestamp` 선택.

## 7. Troubleshooting

### Case 1: Elasticsearch Unhealthy / Exit
- 로그 확인: `AccessDeniedException` -> 권한 문제. `make install-elk` 재실행 시 자동 수정됨.
- 로그 확인: `max virtual memory areas ... too low` -> `vm.max_map_count` 설정 필요.

### Case 2: Kibana "Not Ready"
- Elasticsearch가 부팅 중일 때 발생. 1~2분 대기.

### Case 3: Logstash에서 로그가 안 보임
- 5044 포트 확인.
- `ai4infra-filebeat` 로그 확인: `Connection refused` 등이 없는지 체크.
- 파이프라인 설정(`config/logstash/pipeline/logstash.conf`)의 JSON 필터 확인.
