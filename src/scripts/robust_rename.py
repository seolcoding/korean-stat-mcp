#!/usr/bin/env python3
import os
import unicodedata
from pathlib import Path
import subprocess

def robust_rename(directory):
    """파일명을 강제로 NFC로 변환"""
    
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"디렉토리가 존재하지 않습니다: {directory}")
        return
    
    # 백업 파일들 먼저 원복
    print("=== 백업 파일 원복 중 ===")
    for backup in dir_path.glob("_backup_*"):
        original_name = backup.name.replace("_backup_", "")
        new_path = backup.parent / original_name
        if not new_path.exists():
            backup.rename(new_path)
            print(f"✅ 백업 파일 원복: {backup.name} → {original_name}")
    
    # convmv 도구 사용 (macOS에 내장)
    print("\n=== convmv를 사용한 파일명 변환 ===")
    try:
        # NFD에서 NFC로 변환
        cmd = [
            'convmv', '-f', 'utf-8', '-t', 'utf-8',
            '--nfc', '-r', '--notest', 
            str(directory)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print("convmv 출력:")
        print(result.stdout)
        if result.stderr:
            print("에러:", result.stderr)
    except FileNotFoundError:
        print("convmv가 설치되어 있지 않습니다. Homebrew로 설치해주세요: brew install convmv")
    
    # 최종 울산 파일 확인
    print("\n=== 울산 파일 최종 확인 ===")
    ulsan_files = []
    for file_path in dir_path.iterdir():
        if file_path.is_file() and '울산' in unicodedata.normalize('NFC', file_path.name):
            ulsan_files.append(file_path.name)
    
    print(f"울산 파일 개수: {len(ulsan_files)}")
    for f in sorted(ulsan_files):
        print(f"  - {f}")
        
    # Python으로 grep 확인
    print("\n=== Python grep 테스트 ===")
    count = 0
    for file_path in dir_path.iterdir():
        if file_path.is_file():
            nfc_name = unicodedata.normalize('NFC', file_path.name)
            if '울산' in nfc_name:
                count += 1
    print(f"Python에서 찾은 울산 파일: {count}개")

if __name__ == "__main__":
    robust_rename("/Users/sdh/Dev/02_production_projects/kosis-data-processor/logo2")