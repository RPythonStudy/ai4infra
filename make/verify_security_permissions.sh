#!/bin/bash
# AI4RM 서비스 권한 검증 스크립트
# 모든 서비스의 권한이 보안 정책에 맞는지 확인

check_permissions() {
    local service=$1
    local expected_docker="750"
    local expected_backup="700" 
    local expected_scripts="700"
    
    echo "=== $service 서비스 권한 검증 ==="
    
    # Docker 디렉토리 권한 확인
    local docker_perm=$(stat -c "%a" "/opt/ai4rm/docker/$service" 2>/dev/null || echo "없음")
    echo "Docker 디렉토리: $docker_perm (예상: $expected_docker)"
    
    # 백업 디렉토리 권한 확인  
    local backup_perm=$(stat -c "%a" "/opt/ai4rm/.backup/$service" 2>/dev/null || echo "없음")
    echo "백업 디렉토리: $backup_perm (예상: $expected_backup)"
    
    # 스크립트 권한 확인
    if [ -d "/opt/ai4rm/scripts/$service" ]; then
        echo "스크립트 파일들:"
        ls -l /opt/ai4rm/scripts/$service/*.sh 2>/dev/null || echo "스크립트 없음"
    fi
    
    echo ""
}

# AI4RM 핵심 서비스들 권한 검증
services=("bitwarden" "vault" "keycloak" "elk" "openldap")

for service in "${services[@]}"; do
    check_permissions "$service"
done

echo "=== 보안 정책 준수 확인 ==="
echo "- 700: 소유자만 읽기/쓰기/실행 (스크립트, 백업)"
echo "- 750: 소유자 모든권한, 그룹 읽기/실행 (Docker)"
echo "- 모든 변경사항은 /var/log/ai4rm/security-audit.log에 기록"
