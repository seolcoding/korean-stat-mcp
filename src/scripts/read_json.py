import pandas as pd

df = pd.read_json('/workspaces/kosis-data-processor/kosis_data/density.json', encoding='utf-8')
print(df.head(), df.info, df.columns, sep='\n')