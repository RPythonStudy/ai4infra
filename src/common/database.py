"""
파일명: src/common/database.py
목적: 데이터베이스 연결 및 쿼리 실행 담당
기능: 
- PostgreSQL 데이터베이스에 연결
- SQL 쿼리 실행 및 결과 반환
- 에러 발생 시 로깅
변경이력:
  - 2025-09-01: 최초 생성 (BenKorea)
"""

import psycopg2
import os
from common.logger import log_error, log_debug
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """표준 데이터베이스 연결을 반환합니다."""
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "ai4ref"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            port=os.getenv("DB_PORT", "5432")
        )
        log_debug("데이터베이스 연결 성공")
        return conn
    except psycopg2.Error as e:
        log_error(f"데이터베이스 연결 실패: {e}")
        raise

def execute_query(query: str, params=None, fetch_one=False, fetch_all=False):
    """쿼리 실행 헬퍼 함수"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(query, params)
        
        result = None
        if fetch_one:
            result = cur.fetchone()
        elif fetch_all:
            result = cur.fetchall()
        
        conn.commit()
        cur.close()
        conn.close()
        
        return result
        
    except psycopg2.Error as e:
        log_error(f"쿼리 실행 오류: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise

def execute_many(query: str, data_list):
    """배치 삽입 헬퍼 함수"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.executemany(query, data_list)
        
        conn.commit()
        affected_rows = cur.rowcount
        cur.close()
        conn.close()
        
        return affected_rows
        
    except psycopg2.Error as e:
        log_error(f"배치 실행 오류: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
