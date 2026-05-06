"""
Channel 判定逻辑单元测试
运行方式: python scripts/test_channel_judge.py
"""

import sys
import os
import unittest
import tempfile
from pathlib import Path

# 添加项目根目录到路径
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

# 导入待测试函数（直接读取源码避免重复import）
import importlib.util


def load_module_from_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# 动态加载 run_etl 模块（复用其中的函数）
etl = load_module_from_source("run_etl", SCRIPT_DIR / "run_etl.py")


class TestMatchChannelPriority(unittest.TestCase):
    """验证 9 层漏斗判定优先级"""

    def _make_df(self, rows):
        """快捷构造测试DataFrame（包含actual_amount列）"""
        return pd.DataFrame(rows)

    def test_p1_uxian_sample(self):
        """P1: spu_type含'小样-u先' → channel='U先派样'"""
        df = self._make_df({
            'order_id': ['1', '2'],
            'product_id': ['p1', 'p2'],
            'product_title': ['标题A', '标题B'],
            'spu_type': ['小样-u先-佳琦推荐', '正装-热销'],
            'actual_amount': [10.0, 10.0],
        })
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[])
        self.assertEqual(result.loc[result['order_id'] == '1', 'channel'].iloc[0], 'U先派样')

    def test_p2_baiBu_sample(self):
        """P2: spu_type含'小样-百亿补贴' → channel='百补派样'"""
        df = self._make_df({
            'order_id': ['1'],
            'product_id': ['p1'],
            'product_title': ['标题'],
            'spu_type': ['小样-百亿补贴-品牌日'],
            'actual_amount': [10.0],
        })
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[])
        self.assertEqual(result['channel'].iloc[0], '百补派样')

    def test_p3_zengpin(self):
        """P3: spu_type含'小样'但非P1/P2 → channel='赠品&0.01渠道'"""
        df = self._make_df({
            'order_id': ['1'],
            'product_id': ['p1'],
            'product_title': ['标题'],
            'spu_type': ['小样-限时赠品'],
            'actual_amount': [10.0],
        })
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[])
        self.assertEqual(result['channel'].iloc[0], '赠品&0.01渠道')

    def test_p1_not_overridden_by_p4(self):
        """P1 不被 P4 覆盖：spu_type='小样-u先' + product_title含'佳琦' → 必须是'U先派样'"""
        df = self._make_df({
            'order_id': ['1'],
            'product_id': ['p1'],
            'product_title': ['李佳琦直播间小样-u先'],
            'spu_type': ['小样-u先'],
            'actual_amount': [10.0],
        })
        # 传入含'佳琦'的keyword_rules，但P1应该保持不被覆盖
        keyword_rules = [('佳琦', '微博')]
        result = etl.match_channel(df.copy(), keyword_rules=keyword_rules, id_rules=[])
        self.assertEqual(result['channel'].iloc[0], 'U先派样')

    def test_p1_not_overridden_by_p3_amount(self):
        """P1 不被 P3 的 actual_amount<4 覆盖：spu_type='小样-u先' + actual_amount=1.0 → 必须是'U先派样'"""
        df = self._make_df({
            'order_id': ['1'],
            'product_id': ['p1'],
            'product_title': ['标题'],
            'spu_type': ['小样-u先'],
            'actual_amount': [1.0],  # < 4，但不应被P3覆盖
        })
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[])
        self.assertEqual(result['channel'].iloc[0], 'U先派样')

    def test_p1_huiyuan_keyword(self):
        """P1 新增关键词：product_title含'会员尝鲜' → channel='U先派样'"""
        df = self._make_df({
            'order_id': ['1'],
            'product_id': ['p1'],
            'product_title': ['芙清会员尝鲜装'],
            'spu_type': ['正装-热销'],  # spu_type不匹配，靠关键词命中
            'actual_amount': [10.0],
        })
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[])
        self.assertEqual(result['channel'].iloc[0], 'U先派样')

    def test_p7_直播(self):
        """P7: order_id在live_order_ids中 → channel='直播'"""
        df = self._make_df({
            'order_id': ['1', '2'],
            'product_id': ['p1', 'p2'],
            'product_title': ['普通正装商品', '另一种正装商品'],
            'spu_type': ['正装-经典款', '正装-热销'],
            'actual_amount': [10.0, 10.0],
        })
        live_ids = {'1'}  # 只有 order_id='1' 在直播集合中
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[], taoke_order_ids=set(), live_order_ids=live_ids)
        # order_id='1' 命中直播 → 直播
        self.assertEqual(result.loc[result['order_id'] == '1', 'channel'].iloc[0], '直播')
        # order_id='2' spu_type含正装且非直播，走P8 → 货架
        self.assertEqual(result.loc[result['order_id'] == '2', 'channel'].iloc[0], '货架')

    def test_p8_货架(self):
        """P8: spu_type含'正装'且未被P1-P7命中 → channel='货架'"""
        df = self._make_df({
            'order_id': ['1'],
            'product_id': ['p_no_match'],
            'product_title': ['普通正装商品'],
            'spu_type': ['正装-经典款'],
            'actual_amount': [10.0],
        })
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[], taoke_order_ids=set(), live_order_ids=set())
        self.assertEqual(result['channel'].iloc[0], '货架')

    def test_p9_nan_and_no_zhengzhuang(self):
        """P9: spu_type为NaN或不包含'正装' → channel='其他'（默认值）"""
        df_nan = self._make_df({
            'order_id': ['1'],
            'product_id': ['p1'],
            'product_title': ['商品'],
            'spu_type': [None],
            'actual_amount': [10.0],
        })
        df_empty = self._make_df({
            'order_id': ['2'],
            'product_id': ['p2'],
            'product_title': ['商品'],
            'spu_type': [''],
            'actual_amount': [10.0],
        })
        result_nan = etl.match_channel(df_nan.copy(), keyword_rules=[], id_rules=[], taoke_order_ids=set(), live_order_ids=set())
        result_empty = etl.match_channel(df_empty.copy(), keyword_rules=[], id_rules=[], taoke_order_ids=set(), live_order_ids=set())
        self.assertEqual(result_nan['channel'].iloc[0], '其他')
        self.assertEqual(result_empty['channel'].iloc[0], '其他')

    def test_p5_taoke(self):
        """P5: order_id在淘客集合中 → channel='淘客'"""
        df = self._make_df({
            'order_id': ['TK001', 'TK002', 'TK003'],
            'product_id': ['p1', 'p2', 'p3'],
            'product_title': ['商品A', '商品B', '商品C'],
            'spu_type': ['正装-热销', '小样-赠品', '正装-经典'],
            'actual_amount': [10.0, 10.0, 10.0],
        })
        taoke_ids = {'TK001', 'TK003'}  # 只有TK001和TK003是淘客
        result = etl.match_channel(df.copy(), keyword_rules=[], id_rules=[], taoke_order_ids=taoke_ids, live_order_ids=set())
        # TK001是淘客（spu_type含正装本应P8，但P5优先）
        self.assertEqual(result.loc[result['order_id'] == 'TK001', 'channel'].iloc[0], '淘客')
        # TK002不是淘客，spu_type='小样-赠品'走P3 → 赠品&0.01渠道
        self.assertEqual(result.loc[result['order_id'] == 'TK002', 'channel'].iloc[0], '赠品&0.01渠道')
        # TK003是淘客
        self.assertEqual(result.loc[result['order_id'] == 'TK003', 'channel'].iloc[0], '淘客')


class TestLoadTaokeOrderIds(unittest.TestCase):
    """验证淘客订单号读取（含制表符清洗、去重）"""

    def setUp(self):
        """创建临时CSV测试文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.etl = etl
        # 临时覆盖数据源路径（测试完后恢复）
        self._orig_source = getattr(etl, 'TAOKE_DATA_SOURCE', None)
        self._orig_cache = getattr(etl, '_TAOKE_ORDER_IDS_CACHE', None)

    def tearDown(self):
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        # 恢复全局缓存
        if self._orig_cache is not None:
            etl._TAOKE_ORDER_IDS_CACHE = self._orig_cache
        if self._orig_source is not None:
            etl.TAOKE_DATA_SOURCE = self._orig_source

    def test_tab_character_cleaning(self):
        """验证CSV中的制表符\\t被清洗"""
        csv_path = Path(self.temp_dir) / "test_tab.csv"
        csv_path.write_text("订单编号,淘宝父订单编号\n1,TK100\t\n2,TK200\t\n3,TK300\n")
        etl.TAOKE_DATA_SOURCE = Path(self.temp_dir)
        etl._TAOKE_ORDER_IDS_CACHE = None  # 清除缓存

        ids = etl.load_taoke_order_ids()
        self.assertIn('TK100', ids)
        self.assertIn('TK200', ids)
        self.assertIn('TK300', ids)
        # 不应包含带制表符的版本
        self.assertNotIn('TK100\t', ids)

    def test_deduplication(self):
        """验证去重生效"""
        csv_path = Path(self.temp_dir) / "test_dup.csv"
        csv_path.write_text("订单编号,淘宝父订单编号\n1,TK100\n2,TK100\n3,TK200\n")
        etl.TAOKE_DATA_SOURCE = Path(self.temp_dir)
        etl._TAOKE_ORDER_IDS_CACHE = None

        ids = etl.load_taoke_order_ids()
        self.assertEqual(len(ids), 2)  # TK100只应出现一次

    def test_empty_values_filtered(self):
        """验证空值和空白被过滤"""
        csv_path = Path(self.temp_dir) / "test_empty.csv"
        csv_path.write_text("订单编号,淘宝父订单编号\n1,TK100\n2,\n3,  \n4,\t\n5,TK200\n")
        etl.TAOKE_DATA_SOURCE = Path(self.temp_dir)
        etl._TAOKE_ORDER_IDS_CACHE = None

        ids = etl.load_taoke_order_ids()
        self.assertEqual(len(ids), 2)
        self.assertIn('TK100', ids)
        self.assertIn('TK200', ids)
        self.assertNotIn('', ids)
        self.assertNotIn('  ', ids)


class TestUpdateTaokeChannelBatch(unittest.TestCase):
    """验证分批UPDATE逻辑"""

    def setUp(self):
        self.temp_db = tempfile.mktemp(suffix='.duckdb')
        self.etl = etl
        # 替换DUCKDB路径
        self._orig_path = getattr(etl, 'DUCKDB_PATH', None)
        etl.DUCKDB_PATH = Path(self.temp_db)

        # 创建测试表
        import duckdb
        conn = duckdb.connect(self.temp_db)
        conn.execute("""
            CREATE TABLE orders (
                order_id VARCHAR,
                channel VARCHAR
            )
        """)
        # 插入测试数据：3条非淘客 + 2条已是淘客
        for oid in ['TK001', 'TK002', 'TK003', 'TK004', 'TK005']:
            ch = '淘客' if oid in ('TK004', 'TK005') else '其他'
            conn.execute("INSERT INTO orders VALUES (?, ?)", [oid, ch])
        conn.close()

    def tearDown(self):
        import duckdb
        conn = duckdb.connect(self.temp_db)
        conn.execute("DROP TABLE IF EXISTS orders")
        conn.close()
        if self._orig_path is not None:
            etl.DUCKDB_PATH = self._orig_path
        else:
            import os
            os.remove(self.temp_db)

    def test_batch_update_with_unmark(self):
        """验证淘客标记支持新增 + 取消：文件替换后旧标记应被清除"""
        # 清除缓存以确保能重新加载
        self.etl._TAOKE_ORDER_IDS_CACHE = None

        # 创建一个临时淘客数据文件（只包含 TK001-TK003，不含 TK004-TK005）
        temp_dir = tempfile.mkdtemp()
        csv_path = Path(temp_dir) / "taoke.csv"
        csv_path.write_text("订单编号,淘宝父订单编号\n1,TK001\n2,TK002\n3,TK003\n")
        self.etl.TAOKE_DATA_SOURCE = Path(temp_dir)

        # 运行更新
        self.etl.update_taoke_channel()

        # 验证结果
        import duckdb
        conn = duckdb.connect(self.temp_db, read_only=True)
        result = conn.execute(
            "SELECT order_id, channel FROM orders ORDER BY order_id"
        ).fetchall()
        conn.close()

        expected = [
            ('TK001', '淘客'),  # 新文件中有 → 标记为淘客
            ('TK002', '淘客'),  # 新文件中有 → 标记为淘客
            ('TK003', '淘客'),  # 新文件中有 → 标记为淘客
            ('TK004', '其他'),  # 原本淘客但新文件中无 → 取消标记
            ('TK005', '其他'),  # 原本淘客但新文件中无 → 取消标记
        ]
        self.assertEqual(result, expected)

        # 清理
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
