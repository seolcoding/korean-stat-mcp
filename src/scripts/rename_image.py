import json
import os
from pathlib import Path
import unicodedata

files = os.listdir("/Users/sdh/Dev/02_production_projects/kosis-data-processor/logo2")

print(len(files))
print(files[0])
assert len(files) == 229

with open(
    "/Users/sdh/Dev/02_production_projects/kosis-data-processor/data/sido_sigungu.json",
    "r",
) as f:
    data = json.load(f)

# error_list = []

# for sido in data:
#     for sigungu in data[sido]:
#         try:
#             print(sido, sigungu)
#             os.rename(
#                 f"/Users/sdh/Dev/02_production_projects/kosis-data-processor/downloaded_logos/{sigungu}.png",
#                 f"/Users/sdh/Dev/02_production_projects/kosis-data-processor/downloaded_logos/{sido}_{sigungu}.png",
#             )
#         except FileNotFoundError:
#             print(f"File not found: {sido}_{sigungu}.png")
#             error_list.append(f"{sido}_{sigungu}.png")
#             continue

# files = os.listdir(
#     "/Users/sdh/Dev/02_production_projects/kosis-data-processor/downloaded_logos"
# )

# 파일명을 NFC로 정규화하여 일관성 있게 처리
file_stems = [unicodedata.normalize('NFC', Path(file).stem) for file in files]
file_stems.sort()

count = 0
for i in file_stems:
    print(count, " : ", i)
    count += 1

print(len(file_stems))
assert len(file_stems) == 229, f"file_stems: {len(file_stems)}"

# 울산 파일 확인
ulsan_files = [f for f in file_stems if "울산" in f]
print(f"\n울산 관련 파일들 ({len(ulsan_files)}개):")
for f in ulsan_files:
    print(f"  - {f}")

# 이제 모든 파일명이 NFC로 정규화되어 있으므로 직접 확인
assert "울산광역시_북구" in file_stems

excluded = []
for sido in data:
    for sigungu in data[sido]:
        if f"{sido}_{sigungu}" not in file_stems:
            excluded.append(f"{sido}_{sigungu}")
print("=" * 100)
for i in excluded:
    print(i)
