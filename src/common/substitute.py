"""
파일명: src/common/substitute.py
기능:
  - 환경변수 치환: ${VAR} → os.environ['VAR']
전제조건:
  - os.environ 에 치환 대상 환경변수가 미리 설정되어 있어야 함
변경이력:
  - 2025-11-25: 최초 구현 (BenKorea)
"""

import os

def substitute_env(value):
    """
    재귀적으로 환경변수 치환을 수행하는 함수.

    지원하는 입력 타입:
        - str
        - dict
        - list

    동작:
        - 문자열(str):
            문자열 내부에서 ${VAR} 패턴을 찾아 os.environ['VAR'] 값으로 치환한다.
        - 딕셔너리(dict):
            모든 value에 대해 substitute_env()를 재귀 호출하여 전체 구조를 치환한다.
        - 리스트(list):
            모든 원소에 substitute_env()를 재귀 호출하여 리스트 내부도 치환한다.
        - 기타 타입(int, float, bool, None 등):
            치환 대상이 아니므로 그대로 반환한다.

    반환:
        입력 데이터 구조와 동일한 타입을 유지하며,
        ${VAR} 패턴이 환경변수 값으로 치환된 결과를 반환한다.
    """

    # 문자열 처리
    if isinstance(value, str):
        for k, v in os.environ.items():
            value = value.replace(f"${{{k}}}", v)
        return value

    # 딕셔너리 처리 (재귀)
    if isinstance(value, dict):
        return {key: substitute_env(val) for key, val in value.items()}

    # 리스트 처리 (재귀)
    if isinstance(value, list):
        return [substitute_env(v) for v in value]

    # 치환 대상 없음
    return value
