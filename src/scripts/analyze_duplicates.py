#!/usr/bin/env python3
import os
import unicodedata
from pathlib import Path
from collections import defaultdict

def analyze_duplicates(directory):
    """디렉토리 내 중복 파일명 분석"""
    
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"디렉토리가 존재하지 않습니다: {directory}")
        return
    
    # 모든 파일 분석
    files_by_normalized = defaultdict(list)
    
    for file_path in dir_path.iterdir():
        if file_path.is_file():
            original_name = file_path.name
            nfc_name = unicodedata.normalize('NFC', original_name)
            nfd_name = unicodedata.normalize('NFD', original_name)
            
            files_by_normalized[nfc_name].append({
                'path': file_path,
                'original': original_name,
                'is_nfc': original_name == nfc_name,
                'is_nfd': original_name == nfd_name,
                'bytes': original_name.encode('utf-8')
            })
    
    # 중복 찾기
    duplicates = {k: v for k, v in files_by_normalized.items() if len(v) > 1}
    
    if duplicates:
        print(f"=== 중복 파일 발견: {len(duplicates)}개 ===\n")
        for normalized_name, files in duplicates.items():
            print(f"정규화된 이름: {normalized_name}")
            for i, file_info in enumerate(files):
                print(f"  파일 {i+1}:")
                print(f"    원본: {file_info['original']}")
                print(f"    NFC: {file_info['is_nfc']}, NFD: {file_info['is_nfd']}")
                print(f"    바이트: {file_info['bytes'][:50]}...")
            print()
    
    # 울산 파일 특별 분석
    print("=== 울산 파일 분석 ===")
    for name, files in files_by_normalized.items():
        if '울산' in name:
            print(f"\n파일명: {name}")
            for file_info in files:
                print(f"  원본: {file_info['original']}")
                print(f"  NFC: {file_info['is_nfc']}, NFD: {file_info['is_nfd']}")
                
    # NFD로 인코딩된 파일들만 찾기
    nfd_files = []
    for name, files in files_by_normalized.items():
        for file_info in files:
            if file_info['is_nfd'] and not file_info['is_nfc']:
                nfd_files.append(file_info['path'])
    
    if nfd_files:
        print(f"\n=== NFD로 인코딩된 파일: {len(nfd_files)}개 ===")
        for f in nfd_files[:10]:  # 처음 10개만 표시
            print(f"  - {f.name}")
            
    # 직접 울산 파일 검색
    print("\n=== 직접 울산 검색 ===")
    ulsan_count = 0
    for file_path in dir_path.iterdir():
        if file_path.is_file():
            # 다양한 방법으로 울산 검색
            if '울산' in file_path.name or '울산' in unicodedata.normalize('NFC', file_path.name):
                ulsan_count += 1
                print(f"  {ulsan_count}. {file_path.name}")

if __name__ == "__main__":
    analyze_duplicates("/Users/sdh/Dev/02_production_projects/kosis-data-processor/logo2")