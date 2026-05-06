import duckdb
import pandas as pd

conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)

top_ids = [649010984532, 636178986824, 663972438411, 673750286742, 664733776944,
           675303968215, 669406755965, 658001276157, 630177025590, 607683727078]

spu_df = pd.read_csv('/Users/hutou/Desktop/fuqin date/芙清CRM数据库/芙清crm原始数据库/天猫_spu单品匹配表_数据表.csv')
spu_df.columns = ['product_id','cat','sales','type','tier','single','single_sub','jx','spec','start','end','owner','parent']
spu_ids = set(spu_df['product_id'].astype(str).unique())
print('SPU映射表总ID数: {}'.format(len(spu_ids)))
print()

for pid in top_ids:
    pid_str = str(pid)
    in_spu = pid_str in spu_ids
    if in_spu:
        records = spu_df[spu_df['product_id'].astype(str) == pid_str]
        print('{} | SPU表存在 | {}条记录'.format(pid, len(records)))
        for _, row in records.iterrows():
            print('  {} | {} ~ {}'.format(row['single_sub'], row['start'], row['end']))
    else:
        print('{} | SPU表中不存在'.format(pid))

conn.close()
