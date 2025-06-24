#!/usr/bin/env python3
import os
import unicodedata
from pathlib import Path

def fix_filename_encoding(directory):
    """디렉토리 내 모든 파일의 이름을 NFC로 정규화"""
    
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"디렉토리가 존재하지 않습니다: {directory}")
        return
    
    files_renamed = 0
    errors = []
    
    # 모든 파일 목록 가져오기
    for file_path in dir_path.iterdir():
        if file_path.is_file():
            old_name = file_path.name
            # NFC 정규화 (macOS의 NFD를 NFC로 변환)
            new_name = unicodedata.normalize('NFC', old_name)
            
            if old_name != new_name:
                try:
                    new_path = file_path.parent / new_name
                    # 이미 같은 이름의 파일이 있는지 확인
                    if new_path.exists():
                        print(f"⚠️  이미 존재함: {new_name}")
                        errors.append((old_name, "파일이 이미 존재"))
                    else:
                        file_path.rename(new_path)
                        print(f"✅ 변경됨: {old_name} → {new_name}")
                        files_renamed += 1
                except Exception as e:
                    print(f"❌ 오류: {old_name} - {str(e)}")
                    errors.append((old_name, str(e)))
    
    print(f"\n총 {files_renamed}개 파일 이름 변경됨")
    if errors:
        print(f"오류 발생: {len(errors)}개")
        for filename, error in errors:
            print(f"  - {filename}: {error}")
    
    # 변경 후 울산 파일 확인
    print("\n=== 울산 관련 파일 확인 ===")
    ulsan_files = list(dir_path.glob("*울산*"))
    print(f"울산 파일 개수: {len(ulsan_files)}")
    for f in sorted(ulsan_files):
        print(f"  - {f.name}")

if __name__ == "__main__":
    # logo2 디렉토리의 파일명 정규화
    fix_filename_encoding("/Users/sdh/Dev/02_production_projects/kosis-data-processor/logo2")