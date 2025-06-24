#!/usr/bin/env python3
import os
import unicodedata
from pathlib import Path
import shutil

def analyze_and_convert(directory):
    """디렉토리 내 파일들의 인코딩을 분석하고 다수결로 통일"""
    
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"디렉토리가 존재하지 않습니다: {directory}")
        return
    
    # 모든 파일 분석
    nfc_count = 0
    nfd_count = 0
    files_info = []
    
    for file_path in dir_path.iterdir():
        if file_path.is_file():
            original_name = file_path.name
            nfc_name = unicodedata.normalize('NFC', original_name)
            nfd_name = unicodedata.normalize('NFD', original_name)
            
            is_nfc = original_name == nfc_name
            is_nfd = original_name == nfd_name
            
            if is_nfc:
                nfc_count += 1
            elif is_nfd:
                nfd_count += 1
                
            files_info.append({
                'path': file_path,
                'original': original_name,
                'is_nfc': is_nfc,
                'is_nfd': is_nfd,
                'nfc_name': nfc_name,
                'nfd_name': nfd_name
            })
    
    print(f"=== 인코딩 분석 결과 ===")
    print(f"전체 파일 수: {len(files_info)}")
    print(f"NFC 인코딩: {nfc_count}개")
    print(f"NFD 인코딩: {nfd_count}개")
    print(f"기타: {len(files_info) - nfc_count - nfd_count}개")
    
    # 다수결로 타겟 인코딩 결정
    target_encoding = 'NFC' if nfc_count >= nfd_count else 'NFD'
    print(f"\n타겟 인코딩: {target_encoding}")
    
    # 변환 실행
    converted_count = 0
    errors = []
    
    print(f"\n=== {target_encoding}로 변환 시작 ===")
    
    for file_info in files_info:
        file_path = file_info['path']
        original_name = file_info['original']
        
        if target_encoding == 'NFC':
            new_name = file_info['nfc_name']
            needs_conversion = not file_info['is_nfc']
        else:
            new_name = file_info['nfd_name']
            needs_conversion = not file_info['is_nfd']
        
        if needs_conversion and original_name != new_name:
            try:
                new_path = file_path.parent / new_name
                
                # 이미 존재하는 경우 백업
                if new_path.exists() and new_path != file_path:
                    backup_name = f"_backup_{new_name}"
                    backup_path = file_path.parent / backup_name
                    shutil.move(str(new_path), str(backup_path))
                    print(f"  백업: {new_name} → {backup_name}")
                
                file_path.rename(new_path)
                print(f"✅ 변환: {original_name} → {new_name}")
                converted_count += 1
                
            except Exception as e:
                print(f"❌ 오류: {original_name} - {str(e)}")
                errors.append((original_name, str(e)))
    
    print(f"\n총 {converted_count}개 파일 변환됨")
    if errors:
        print(f"오류 발생: {len(errors)}개")
        for filename, error in errors:
            print(f"  - {filename}: {error}")
    
    # 울산 파일 최종 확인
    print("\n=== 울산 파일 최종 확인 ===")
    ulsan_files = []
    for file_path in dir_path.iterdir():
        if file_path.is_file() and '울산' in file_path.name:
            ulsan_files.append(file_path.name)
    
    print(f"울산 파일 개수: {len(ulsan_files)}")
    for f in sorted(ulsan_files):
        print(f"  - {f}")

if __name__ == "__main__":
    analyze_and_convert("/Users/sdh/Dev/02_production_projects/kosis-data-processor/logo2")