"""
파일명: tests/unit/test_excel_io.py
목적: read_excels 함수의 동작을 단위 테스트로 검증
주요 기능:
- 임시 폴더에 엑셀 파일을 생성하고, read_excels가 올바른 DataFrame 딕셔너리를 반환하는지 확인
변경이력:
  - 2025-09-24: 최초 생성 (BenKorea)
"""

import os
import pandas as pd
import tempfile
from pathlib import Path
from common.excel_io import read_excels

def test_read_excels(tmp_path):
    # 임시 엑셀 파일 생성
    df1 = pd.DataFrame({'a': [1, 2], 'b': [3, 4]})
    df2 = pd.DataFrame({'x': [10, 20], 'y': [30, 40]})
    file1 = tmp_path / 'test1.xlsx'
    file2 = tmp_path / 'test2.xls'
    df1.to_excel(file1, index=False)
    df2.to_excel(file2, index=False)

    # 함수 실행
    result = read_excels(str(tmp_path))

    # 검증
    assert 'test1.xlsx' in result
    assert 'test2.xls' in result
    pd.testing.assert_frame_equal(result['test1.xlsx'], df1)
    pd.testing.assert_frame_equal(result['test2.xls'], df2)

if __name__ == "__main__":
    import tempfile
    test_read_excels(Path(tempfile.mkdtemp()))
    print("테스트 통과!")
