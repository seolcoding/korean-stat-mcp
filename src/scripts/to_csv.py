import os
import pandas as pd

def to_csv(filepath):
    encodings = ['utf-8', 'cp949', 'euc-kr']
    for encoding in encodings:
        try:
            dataframe = pd.read_csv(filepath, encoding=encoding)
            break
        except UnicodeDecodeError:
            print(f"Failed to read {filepath} with encoding {encoding}. Trying next encoding...")
    else:
        raise ValueError(f"Failed to read {filepath} with all encodings: {encodings}")
    dataframe.to_csv(filepath, index=False, encoding='utf-8-sig')
    print(f"Successfully converted {filepath} to UTF-8 with BOM encoding.")

if __name__ == '__main__':
    csv_files = [i for i in os.listdir('data/') if i.endswith('.csv')]
    for csv_file in csv_files:
        to_csv(f'data/{csv_file}')