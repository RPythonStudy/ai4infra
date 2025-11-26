"""
파일명: tests/unit/test_substitute.py
목적: substitute_env() 함수 단위 테스트
기능:
  - 환경변수 치환 로직의 정확성 검증
  - 다양한 데이터 타입(str, dict, list, nested) 테스트
  - 엣지 케이스 및 에러 처리 검증
변경이력:
  - 2025-11-26: 최초 구현 (BenKorea)
"""

import os
import pytest
from common.substitute import substitute_env


class TestSubstituteEnv:
    """substitute_env 함수 테스트 클래스"""

    def setup_method(self):
        """각 테스트 전 환경변수 설정"""
        os.environ['TEST_VAR'] = 'test_value'
        os.environ['PROJECT_NAME'] = 'rpy-quarto-template'
        os.environ['LOG_PATH'] = '/var/log/app'
        os.environ['PORT'] = '8080'

    def teardown_method(self):
        """각 테스트 후 환경변수 정리"""
        for key in ['TEST_VAR', 'PROJECT_NAME', 'LOG_PATH', 'PORT']:
            os.environ.pop(key, None)

    # ========== 문자열 치환 테스트 ==========
    
    def test_substitute_simple_string(self):
        """단순 문자열 내 환경변수 치환"""
        result = substitute_env("Value is ${TEST_VAR}")
        assert result == "Value is test_value"

    def test_substitute_multiple_vars(self):
        """하나의 문자열에 여러 환경변수 치환"""
        result = substitute_env("${PROJECT_NAME} runs on port ${PORT}")
        assert result == "rpy-quarto-template runs on port 8080"

    def test_substitute_repeated_var(self):
        """동일 환경변수 반복 치환"""
        result = substitute_env("${TEST_VAR} and ${TEST_VAR}")
        assert result == "test_value and test_value"

    def test_substitute_no_vars(self):
        """환경변수 없는 문자열 그대로 반환"""
        result = substitute_env("plain string")
        assert result == "plain string"

    def test_substitute_undefined_var(self):
        """미정의 환경변수는 치환되지 않음"""
        result = substitute_env("${UNDEFINED_VAR}")
        assert result == "${UNDEFINED_VAR}"

    # ========== 딕셔너리 치환 테스트 ==========

    def test_substitute_dict(self):
        """딕셔너리 값 치환"""
        input_dict = {
            'name': '${PROJECT_NAME}',
            'port': '${PORT}',
            'static': 'no_substitution'
        }
        result = substitute_env(input_dict)
        assert result == {
            'name': 'rpy-quarto-template',
            'port': '8080',
            'static': 'no_substitution'
        }

    def test_substitute_nested_dict(self):
        """중첩 딕셔너리 재귀 치환"""
        input_dict = {
            'app': {
                'name': '${PROJECT_NAME}',
                'logging': {
                    'path': '${LOG_PATH}'
                }
            }
        }
        result = substitute_env(input_dict)
        assert result['app']['name'] == 'rpy-quarto-template'
        assert result['app']['logging']['path'] == '/var/log/app'

    # ========== 리스트 치환 테스트 ==========

    def test_substitute_list(self):
        """리스트 원소 치환"""
        input_list = ['${PROJECT_NAME}', '${PORT}', 'static']
        result = substitute_env(input_list)
        assert result == ['rpy-quarto-template', '8080', 'static']

    def test_substitute_nested_list(self):
        """중첩 리스트 재귀 치환"""
        input_list = [
            '${TEST_VAR}',
            ['${PROJECT_NAME}', '${PORT}']
        ]
        result = substitute_env(input_list)
        assert result == [
            'test_value',
            ['rpy-quarto-template', '8080']
        ]

    # ========== 복합 구조 테스트 ==========

    def test_substitute_complex_structure(self):
        """딕셔너리 + 리스트 혼합 구조 치환"""
        input_data = {
            'project': '${PROJECT_NAME}',
            'servers': [
                {'host': 'localhost', 'port': '${PORT}'},
                {'host': 'prod', 'port': '443'}
            ],
            'paths': {
                'logs': ['${LOG_PATH}/app.log', '${LOG_PATH}/error.log']
            }
        }
        result = substitute_env(input_data)
        
        assert result['project'] == 'rpy-quarto-template'
        assert result['servers'][0]['port'] == '8080'
        assert result['servers'][1]['port'] == '443'
        assert result['paths']['logs'][0] == '/var/log/app/app.log'
        assert result['paths']['logs'][1] == '/var/log/app/error.log'

    # ========== 기타 타입 테스트 ==========

    def test_substitute_integer(self):
        """정수는 그대로 반환"""
        result = substitute_env(12345)
        assert result == 12345

    def test_substitute_float(self):
        """실수는 그대로 반환"""
        result = substitute_env(3.14)
        assert result == 3.14

    def test_substitute_boolean(self):
        """불린은 그대로 반환"""
        assert substitute_env(True) is True
        assert substitute_env(False) is False

    def test_substitute_none(self):
        """None은 그대로 반환"""
        result = substitute_env(None)
        assert result is None

    # ========== 엣지 케이스 테스트 ==========

    def test_substitute_empty_string(self):
        """빈 문자열 처리"""
        result = substitute_env("")
        assert result == ""

    def test_substitute_empty_dict(self):
        """빈 딕셔너리 처리"""
        result = substitute_env({})
        assert result == {}

    def test_substitute_empty_list(self):
        """빈 리스트 처리"""
        result = substitute_env([])
        assert result == []

    def test_substitute_with_special_chars(self):
        """특수문자 포함 환경변수명"""
        os.environ['TEST_VAR_123'] = 'special_value'
        result = substitute_env("${TEST_VAR_123}")
        assert result == "special_value"
        os.environ.pop('TEST_VAR_123')

    def test_substitute_preserves_original(self):
        """원본 데이터 불변성 확인 (immutability)"""
        original = {'key': '${TEST_VAR}'}
        result = substitute_env(original)
        
        # 원본은 변경되지 않아야 함
        assert original['key'] == '${TEST_VAR}'
        assert result['key'] == 'test_value'
