"""
파일명: src/common/excel_io.py
목적: 지정된 폴더의 엑셀파일의 입출력 담당
기능: 
- input_dir를 인자로 받아 폴더 내 모든 xls/xlsx 파일을 탐색
- Path 객체 및 pandas 라이브러리 사용
- {파일명: 데이터프레임} 형태의 딕셔너리 반환
변경이력:
  - 2025-10-02: 최초 구현 (BenKorea)
"""

import inspect
import os
from pathlib import Path
import pandas as pd
from typing import Dict, Optional
from common.logger import log_error, log_debug, log_info

def read_excels(input_dir: str) -> Dict[str, pd.DataFrame]:
  excel_files = Path(input_dir).rglob("*.xls*")
  dfs = {}
  for file in excel_files:
    try:
      df = pd.read_excel(file)
      dfs[file.name] = df
      log_debug(f"[read_excels] from: {file.name} (shape={df.shape})")
    except Exception as e:
      log_error(f"[{inspect.currentframe().f_code.co_name}] 엑셀 파일 읽기 오류: {file} - {e}")
  return dfs


def save_excels(output_dir: str, dataframes_dict: Dict[str, pd.DataFrame], 
                    prefix: Optional[str] = None) -> None:
    """
    데이터프레임 딕셔너리를 지정된 디렉토리에 엑셀 파일로 저장하는 일반화된 함수.
    
    Args:
        output_dir (str): 저장할 디렉토리 경로
        dataframes_dict (Dict[str, pd.DataFrame]): {파일명: 데이터프레임} 딕셔너리
        prefix (Optional[str]): 파일명 앞에 붙일 접두사 (예: "deid_", "structured_")
        
    Returns:
        None
        
    Raises:
        OSError: 디렉토리 생성 실패시
        Exception: 파일 저장 실패시
        
    Example:
        >>> dfs = {"report1.xlsx": df1, "report2.xlsx": df2}
        >>> save_excel_files("output/", dfs, prefix="deid_")
        # 결과: "output/deid_report1.xlsx", "output/deid_report2.xlsx"
    """
    
    # 유효성 검사
    if not output_dir or not isinstance(output_dir, str) or output_dir.strip() == "":
        log_error("[save_excel_files] output_dir가 설정되지 않았습니다.")
        return
        
    if not dataframes_dict:
        log_info("[save_excel_files] 저장할 데이터가 없습니다.")
        return
    
    # 출력 디렉토리 생성
    try:
        os.makedirs(output_dir, exist_ok=True)
        log_debug(f"[save_excel_files] 출력 디렉토리 준비: {output_dir}")
    except OSError as e:
        log_error(f"[save_excel_files] 디렉토리 생성 실패: {output_dir} - {e}")
        return
    
    # 각 파일 저장
    saved_count = 0
    failed_count = 0
    
    for original_filename, df in dataframes_dict.items():
        try:
            # 파일명 처리 (.xls → .xlsx 변환)
            base_filename = os.path.basename(original_filename)
            if base_filename.endswith('.xls'):
                base_filename = base_filename[:-4] + '.xlsx'
            elif not base_filename.endswith('.xlsx'):
                base_filename = base_filename + '.xlsx'
            
            # 접두사/접미사 추가
            name_parts = []
            if prefix:
                name_parts.append(prefix.rstrip('_'))
            
            # 파일명에서 확장자 분리
            name_without_ext = base_filename.replace('.xlsx', '')
            name_parts.append(name_without_ext)
            
            # 최종 파일명 생성
            final_filename = '_'.join(name_parts) + '.xlsx'
            output_path = os.path.join(output_dir, final_filename)
            
            # 파일 저장
            df.to_excel(output_path, index=False)
            log_debug(f"[save_excel_files] 저장 완료: {output_path}")
            saved_count += 1
            
        except Exception as e:
            log_error(f"[save_excel_files] 저장 실패: {original_filename} - {e}")
            failed_count += 1
    
    # 결과 요약
    log_info(f"[save_excel_files] 저장 완료: {saved_count}개, 실패: {failed_count}개")


