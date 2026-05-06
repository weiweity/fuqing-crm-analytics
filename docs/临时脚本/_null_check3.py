import duckdb

conn = duckdb.connect('data/processed/fuqing_crm.duckdb', read_only=True)

# TOP10 NULL ID的订单时间分布
top_ids = [649010984532, 636178986824, 663972438411, 673750286742, 664733776944,
           675303968215, 669406755965, 658001276157, 630177025590, 607683727078]

print('TOP10 NULL ID 时间范围 + SPU表记录:')
print('=' * 70)

for pid in top_ids:
    pid_str = str(pid)
    # 订单时间范围
    time_info = conn.execute("""
        SELECT
            COUNT(*) as total,
            MIN(pay_time) as earliest,
            MAX(pay_time) as latest,
            COUNT(*) FILTER (WHERE spu_type IS NULL OR spu_type = '') as null_cnt
        FROM orders
        WHERE product_id = '{}'
    """.format(pid_str)).fetchone()

    print()
    print('【{}】'.format(pid))
    print('  总订单: {:,}  |  NULL: {:,}  |  NULL率: {:.1f}%'.format(
        time_info[0], time_info[3], time_info[3]/time_info[0]*100))
    print('  订单时间范围: {} ~ {}'.format(time_info[1], time_info[2]))

conn.close()
