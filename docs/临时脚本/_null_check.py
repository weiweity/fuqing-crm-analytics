import duckdb

conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)

total = conn.execute('SELECT COUNT(*) FROM orders').fetchone()[0]
null_cnt = conn.execute("SELECT COUNT(*) FROM orders WHERE spu_type IS NULL OR spu_type = ''").fetchone()[0]
print(f'总订单: {total:,}')
print(f'spu_type=NULL/空: {null_cnt:,} ({null_cnt/total*100:.2f}%)')
print()

# 按product_id分组看null最多的前30个
rows = conn.execute("""
SELECT
    product_id,
    COUNT(*) as null_cnt,
    COUNT(*) * 1.0 / %d * 100 as pct
FROM orders
WHERE spu_type IS NULL OR spu_type = ''
GROUP BY product_id
ORDER BY null_cnt DESC
LIMIT 30
""" % total).fetchall()

print('TOP30 NULL product_id:')
print(f'{"product_id":<20} {"NULL数":>10} {"占比%":>8}')
print('-' * 42)
for r in rows:
    print(f'{str(r[0]):<20} {r[1]:>10,} {r[2]:>7.3f}%')

# 也看一下这些product_id的总数 vs null数，了解缺口大小
print()
print('TOP10 NULL ID 详情:')
print(f'{"product_id":<20} {"NULL数":>10} {"该ID总订单":>12} {"NULL率":>8}')
print('-' * 55)
top10 = conn.execute("""
SELECT
    o.product_id,
    COUNT(*) FILTER (WHERE o.spu_type IS NULL OR o.spu_type = '') as null_cnt,
    COUNT(*) as total_cnt
FROM orders o
WHERE o.product_id IN (
    SELECT product_id FROM orders
    WHERE spu_type IS NULL OR spu_type = ''
    GROUP BY product_id
    ORDER BY COUNT(*) DESC
    LIMIT 10
)
GROUP BY o.product_id
ORDER BY null_cnt DESC
""").fetchall()
for r in top10:
    print(f'{str(r[0]):<20} {r[1]:>10,} {r[2]:>12,} {r[1]/r[2]*100:>7.1f}%')

conn.close()
