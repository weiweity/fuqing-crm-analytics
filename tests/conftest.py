"""测试 fixtures — 共享 mock 连接工厂

所有 mock_db fixture 返回一个工厂函数，
每次调用创建一个新的 in-memory DuckDB 连接（含测试数据）。

Schema: 与 data/processed/fuqing_crm.duckdb orders 表一致（40列）
关键列顺序:
  0=order_id, 5=pay_time, 8=order_status, 16=amount,
  17=refund_status, 18=refund_amount, 19=actual_amount,
  20=province, 21=city, 29=seller_note, 30=year, 31=month,
  32=is_member, 33=spu_category, 39=channel, 40=is_goujinjin, 41=is_refund
"""
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _create_orders_table(conn):
    """创建 orders 表（与真实 fuqing_crm.duckdb schema 一致，40列）"""
    conn.execute("""
        CREATE TABLE orders (
            order_id             VARCHAR,
            sub_order_id         VARCHAR,
            user_id              VARCHAR,
            user_nickname        VARCHAR,
            order_time           TIMESTAMP,
            pay_time             TIMESTAMP,
            ship_time            TIMESTAMP,
            order_type           VARCHAR,
            order_status         VARCHAR,
            product_id           VARCHAR,
            merchant_code        VARCHAR,
            product_title        VARCHAR,
            sku_id               VARCHAR,
            sku_code             VARCHAR,
            sku_name             VARCHAR,
            quantity             INTEGER,
            amount               DOUBLE,
            refund_status        VARCHAR,
            refund_amount        DOUBLE,
            actual_amount        DOUBLE,
            province             VARCHAR,
            city                 VARCHAR,
            influencer_name      VARCHAR,
            influencer_id       VARCHAR,
            live_room_id        VARCHAR,
            video_id            VARCHAR,
            traffic_source       VARCHAR,
            traffic_type         VARCHAR,
            seller_note          VARCHAR,
            year                 INTEGER,
            month                INTEGER,
            is_member            BOOLEAN,
            spu_category        VARCHAR,
            spu_type            VARCHAR,
            spu_tier            VARCHAR,
            spu_product_class   VARCHAR,
            spu_product_subclass VARCHAR,
            spu_cosmetic        VARCHAR,
            spu_spec            VARCHAR,
            channel              VARCHAR,
            is_goujinjin        BOOLEAN,
            is_refund            BOOLEAN
        )
    """)


# ── breakdown_service 专用数据 ─────────────────────────────────
# 活动期间：2025-06-15~2025-06-20 / 去年同期：2024-06-15~2024-06-20


def _orders_breakdown():
    import duckdb
    conn = duckdb.connect(database=":memory:")
    _create_orders_table(conn)

    n = None
    # Schema: order_id(0), sub_order_id(1), user_id(2), user_nickname(3),
    # order_time(4), pay_time(5), ship_time(6), order_type(7), order_status(8),
    # product_id(9), merchant_code(10), product_title(11), sku_id(12), sku_code(13),
    # sku_name(14), quantity(15), amount(16), refund_status(17), refund_amount(18),
    # actual_amount(19), province(20), city(21), influencer_name(22),
    # influencer_id(23), live_room_id(24), video_id(25), traffic_source(26),
    # traffic_type(27), seller_note(28), year(29), month(30), is_member(31),
    # spu_category(32), spu_type(33), spu_tier(34), spu_product_class(35),
    # spu_product_subclass(36), spu_cosmetic(37), spu_spec(38),
    # channel(39), is_goujinjin(40), is_refund(41)
    orders = [
        # UA: 活跃老客（F>1, R=近1个月），去年有购买记录
        ("OA1","OA1-1","UA","用户A","2025-05-28 09:00","2025-05-28 10:00",n,"普通订单","交易成功",n,n,"产品A","SKU1","SKU001","规格A",1,200,n,0,200,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
        ("OA2","OA2-1","UA","用户A","2025-05-10 09:00","2025-05-10 10:00",n,"普通订单","交易成功",n,n,"产品B","SKU2","SKU002","规格B",1,150,n,0,150,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","面霜","高端","功效类","保湿","50g","货架",False,False),
        # UB: 近2-3个月老客（F=1）
        ("OB1","OB1-1","UB","用户B","2025-03-01 09:00","2025-03-01 10:00",n,"普通订单","交易成功",n,n,"产品C","SKU3","SKU003","规格C",1,100,n,0,100,"北京","北京",n,n,n,n,n,n,n,n,2025,3,True,"护肤","水乳","中端","基础类","补水","100ml","货架",False,False),
        # 去年同期购买（用于计算回购率）
        ("OL1","OL1-1","UA","用户A","2024-06-15 09:00","2024-06-15 10:00",n,"普通订单","交易成功",n,n,"产品D","SKU4","SKU004","规格D",1,150,n,0,150,"上海","上海",n,n,n,n,n,n,n,n,2024,6,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
        ("OL2","OL2-1","UB","用户B","2024-06-15 09:00","2024-06-15 10:00",n,"普通订单","交易成功",n,n,"产品E","SKU5","SKU005","规格E",1,100,n,0,100,"北京","北京",n,n,n,n,n,n,n,n,2024,6,True,"护肤","水乳","中端","基础类","补水","100ml","货架",False,False),
        ("OL3","OL3-1","UC","用户C","2024-06-15 09:00","2024-06-15 10:00",n,"普通订单","交易成功",n,n,"产品F","SKU6","SKU006","规格F",1,200,n,0,200,"广东","广州",n,n,n,n,n,n,n,n,2024,6,True,"护肤","面霜","高端","功效类","保湿","50g","货架",False,False),
        # 新客（首购在活动期间）
        ("ON1","ON1-1","UD","用户D","2025-06-16 09:00","2025-06-16 10:00",n,"普通订单","交易成功",n,n,"产品G","SKU7","SKU007","规格G",1,120,n,0,120,"浙江","杭州",n,n,n,n,n,n,n,n,2025,6,True,"护肤","精华","中端","功效类","美白","30ml","货架",False,False),
        ("ON2","ON2-1","UE","用户E","2025-06-17 09:00","2025-06-17 10:00",n,"普通订单","交易成功",n,n,"产品H","SKU8","SKU008","规格H",1,80,n,0,80,"江苏","南京",n,n,n,n,n,n,n,n,2025,6,True,"护肤","水乳","中端","基础类","补水","100ml","达播",False,False),
        # 退款（is_refund=TRUE）
        ("OR1","OR1-1","UA","用户A","2025-06-18 09:00","2025-06-18 10:00",n,"普通订单","交易成功",n,n,"产品I","SKU9","SKU009","规格I",1,-200,"已退款",200,-200,"上海","上海",n,n,n,n,n,n,n,n,2025,6,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,True),
        # 购物金（is_goujinjin=TRUE）
        ("OG1","OG1-1","UF","用户F","2025-06-19 09:00","2025-06-19 10:00",n,"普通订单","交易成功",n,n,"产品J","SKU10","SKU010","规格J",1,100,n,0,100,"四川","成都",n,n,n,n,n,n,n,n,2025,6,True,"护肤","面霜","高端","功效类","保湿","50g","货架",True,False),
        # 交易关闭
        ("OC1","OC1-1","UG","用户G","2025-06-20 09:00","2025-06-20 10:00",n,"普通订单","交易关闭",n,n,"产品K","SKU11","SKU011","规格K",1,50,n,0,0,"湖北","武汉",n,n,n,n,n,n,n,n,2025,6,True,"护肤","水乳","中端","基础类","补水","100ml","货架",False,False),
    ]

    placeholders = ",".join(["?" for _ in range(42)])
    for row in orders:
        assert len(row) == 42, f"Row {row[0]} has {len(row)} values, expected 42"
        conn.execute(f"INSERT INTO orders VALUES ({placeholders})", list(row))

    conn.execute("""
        CREATE TABLE user_first_purchase (
            user_id VARCHAR PRIMARY KEY, first_pay_date DATE
        )
    """)
    for uid, fpd in [
        ("UD","2025-06-16"), ("UE","2025-06-17"),
        ("UA","2023-01-01"), ("UB","2023-06-01"), ("UC","2024-01-01"),
        ("UF","2023-01-01"), ("UG","2023-01-01"),
    ]:
        conn.execute("INSERT INTO user_first_purchase VALUES (?, ?)", [uid, fpd])

    return conn


# ── rfm_service 专用数据 ─────────────────────────────────────


def _orders_rfm():
    import duckdb
    conn = duckdb.connect(database=":memory:")
    _create_orders_table(conn)

    n = None
    orders = [
        ("O1","O1-1","U1","用户1","2025-05-28 09:00","2025-05-28 10:00",n,"普通订单","交易成功",n,n,"产品A","SKU1","SKU001","规格A",1,150,n,0,150,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
        ("O2","O2-1","U1","用户1","2025-05-28 09:00","2025-05-28 11:00",n,"普通订单","交易成功",n,n,"产品B","SKU2","SKU002","规格B",1,150,n,0,150,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","面霜","高端","功效类","保湿","50g","货架",False,False),
        ("O3","O3-1","U2","用户2","2025-05-29 09:00","2025-05-29 10:00",n,"普通订单","交易成功",n,n,"产品C","SKU3","SKU003","规格C",1,100,n,0,100,"北京","北京",n,n,n,n,n,n,n,n,2025,5,True,"护肤","水乳","中端","基础类","补水","100ml","达播",False,False),
        ("O4","O4-1","U3","用户3","2025-05-30 09:00","2025-05-30 10:00",n,"普通订单","交易成功",n,n,"产品D","SKU4","SKU004","规格D",1,-100,"已退款",100,-100,"广东","广州",n,n,n,n,n,n,n,n,2025,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,True),
        ("O5","O5-1","U4","用户4","2025-05-31 09:00","2025-05-31 10:00",n,"普通订单","交易关闭",n,n,"产品E","SKU5","SKU005","规格E",1,200,n,0,0,"四川","成都",n,n,n,n,n,n,n,n,2025,5,True,"护肤","面霜","中端","功效类","保湿","50g","货架",False,False),
    ]

    placeholders = ",".join(["?" for _ in range(42)])
    for row in orders:
        assert len(row) == 42, f"Row {row[0]} has {len(row)} values, expected 42"
        conn.execute(f"INSERT INTO orders VALUES ({placeholders})", list(row))

    conn.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR, analysis_date DATE, metric_type VARCHAR,
            lookback_days INTEGER, r_segment VARCHAR, f_segment VARCHAR,
            m_segment VARCHAR, r_score INTEGER, f_score INTEGER, m_score INTEGER
        )
    """)
    return conn


# ── rfm_analysis 专用数据 ────────────────────────────────────


def _orders_rfm_analysis():
    import duckdb
    conn = duckdb.connect(database=":memory:")
    _create_orders_table(conn)

    n = None
    orders = [
        # U1: 高价值活跃用户（近1个月，2次购买）
        ("O1","O1-1","U1","用户1","2025-05-28 09:00","2025-05-28 10:00",n,"普通订单","交易成功",n,n,"产品A","SKU1","SKU001","规格A",1,500,n,0,500,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
        ("O2","O2-1","U1","用户1","2025-05-10 09:00","2025-05-10 10:00",n,"普通订单","交易成功",n,n,"产品B","SKU2","SKU002","规格B",1,300,n,0,300,"上海","上海",n,n,n,n,n,n,n,n,2025,5,True,"护肤","面霜","高端","功效类","保湿","50g","货架",False,False),
        # U2: 低频用户（近2个月，1次购买）
        ("O3","O3-1","U2","用户2","2025-04-01 09:00","2025-04-01 10:00",n,"普通订单","交易成功",n,n,"产品C","SKU3","SKU003","规格C",1,100,n,0,100,"北京","北京",n,n,n,n,n,n,n,n,2025,4,True,"护肤","水乳","中端","基础类","补水","100ml","达播",False,False),
        # U3: 沉睡用户（1年前购买）
        ("O4","O4-1","U3","用户3","2024-05-15 09:00","2024-05-15 10:00",n,"普通订单","交易成功",n,n,"产品D","SKU4","SKU004","规格D",1,200,n,0,200,"广东","广州",n,n,n,n,n,n,n,n,2024,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,False),
        # U4: 流失用户（2年前购买）
        ("O5","O5-1","U4","用户4","2023-05-01 09:00","2023-05-01 10:00",n,"普通订单","交易成功",n,n,"产品E","SKU5","SKU005","规格E",1,150,n,0,150,"四川","成都",n,n,n,n,n,n,n,n,2023,5,True,"护肤","面霜","中端","功效类","保湿","50g","货架",False,False),
        # U5: 退款用户
        ("O6","O6-1","U5","用户5","2025-05-28 09:00","2025-05-28 10:00",n,"普通订单","交易成功",n,n,"产品F","SKU6","SKU006","规格F",1,-200,"已退款",200,-200,"湖北","武汉",n,n,n,n,n,n,n,n,2025,5,True,"护肤","精华","高端","功效类","美白","30ml","货架",False,True),
        # U6: 交易关闭
        ("O7","O7-1","U6","用户6","2025-05-28 09:00","2025-05-28 10:00",n,"普通订单","交易关闭",n,n,"产品G","SKU7","SKU007","规格G",1,300,n,0,0,"江苏","南京",n,n,n,n,n,n,n,n,2025,5,True,"护肤","面霜","高端","功效类","保湿","50g","货架",False,False),
    ]

    placeholders = ",".join(["?" for _ in range(42)])
    for row in orders:
        assert len(row) == 42, f"Row {row[0]} has {len(row)} values, expected 42"
        conn.execute(f"INSERT INTO orders VALUES ({placeholders})", list(row))

    conn.execute("""
        CREATE TABLE user_rfm (
            user_id VARCHAR, analysis_date DATE, metric_type VARCHAR,
            lookback_days INTEGER, r_segment VARCHAR, f_segment VARCHAR,
            m_segment VARCHAR, r_score INTEGER, f_score INTEGER, m_score INTEGER
        )
    """)
    for row in [
        ("U1","2025-05-28","GSV",90,"近1个月","F>1","高价值",5,4,5),
        ("U2","2025-05-28","GSV",90,"近2-3个月","F=1","低价值",3,2,2),
        ("U3","2025-05-28","GSV",90,"近7-12个月","F=1","低价值",2,2,2),
        ("U4","2025-05-28","GSV",90,"2年外","F=1","低价值",1,1,1),
        ("U5","2025-05-28","GSV",90,"近1个月","F>1","高价值",5,4,5),
        ("U6","2025-05-28","GSV",90,"近1个月","F=1","中价值",5,1,3),
    ]:
        conn.execute("INSERT INTO user_rfm VALUES (?,?,?,?,?,?,?,?,?,?)", row)

    return conn


# ── pytest fixtures ───────────────────────────────────────────


@pytest.fixture
def mock_orders_breakdown():
    """breakdown_service 用：返回工厂函数，每次调用创建新连接"""
    return _orders_breakdown


@pytest.fixture
def mock_orders_rfm():
    """rfm_service 用：返回工厂函数"""
    return _orders_rfm


@pytest.fixture
def mock_orders_rfm_analysis():
    """rfm_analysis 用：返回工厂函数"""
    return _orders_rfm_analysis
