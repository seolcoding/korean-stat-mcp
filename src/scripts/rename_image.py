import os

files = os.listdir(
    "/Users/sdh/Dev/02_production_projects/kosis-data-processor/downloaded_logos"
)

for file in files:
    if "_1" in file:
        os.rename(
            f"/Users/sdh/Dev/02_production_projects/kosis-data-processor/downloaded_logos/{file}",
            f"/Users/sdh/Dev/02_production_projects/kosis-data-processor/downloaded_logos/{file.replace('_1', '')}",
        )
