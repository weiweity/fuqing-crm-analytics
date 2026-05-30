"""Parquet 缓存填充脚本测试"""
import sys
import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd


class TestFillParquetCache:
    """fill_parquet_cache.py 单元测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_xlsx(self, temp_dir):
        """创建一个测试用的 xlsx 文件"""
        data_source = temp_dir / "source"
        data_source.mkdir()
        xlsx_path = data_source / "test_order.xlsx"
        df = pd.DataFrame({
            '订单编号': ['ORD001', 'ORD002'],
            '用户ID': ['U001', 'U002'],
            '下单时间': ['2026-01-01 10:00:00', '2026-01-02 11:00:00'],
            '实付金额': [100.0, 200.0],
        })
        df.to_excel(xlsx_path, index=False, engine='openpyxl')
        return data_source, xlsx_path

    def test_fill_parquet_cache_basic(self, temp_dir, sample_xlsx):
        """测试基本的 Parquet 缓存填充功能"""
        data_source, xlsx_path = sample_xlsx
        pq_dir = temp_dir / "parquet"
        pq_dir.mkdir()

        # 模拟 config 中的路径
        with patch('scripts.etl.config.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.fill_parquet_cache.PARQUET_DATA_DIR', pq_dir):
            from scripts.etl.fill_parquet_cache import fill_parquet_cache

            converted, skipped, errors = fill_parquet_cache(data_source, "shop")

            # 验证转换结果
            assert converted == 1
            assert skipped == 0
            assert errors == 0

            # 验证 Parquet 文件存在
            pq_files = list((pq_dir / "shop").glob("*.parquet"))
            assert len(pq_files) == 1
            assert pq_files[0].name == "test_order.parquet"

            # 验证 Parquet 内容正确
            df = pd.read_parquet(pq_files[0])
            assert 'order_id' in df.columns
            assert len(df) == 2

    def test_fill_parquet_cache_skip_unchanged(self, temp_dir, sample_xlsx):
        """测试增量检测：文件未变更时跳过"""
        data_source, xlsx_path = sample_xlsx
        pq_dir = temp_dir / "parquet"
        pq_dir.mkdir()

        with patch('scripts.etl.config.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.fill_parquet_cache.PARQUET_DATA_DIR', pq_dir):
            from scripts.etl.fill_parquet_cache import fill_parquet_cache

            # 第一次运行
            converted1, skipped1, _ = fill_parquet_cache(data_source, "shop")
            assert converted1 == 1
            assert skipped1 == 0

            # 第二次运行（文件未变更，应跳过）
            converted2, skipped2, _ = fill_parquet_cache(data_source, "shop")
            assert converted2 == 0
            assert skipped2 == 1

    def test_fill_parquet_cache_force(self, temp_dir, sample_xlsx):
        """测试 --force 参数：忽略 mtime，强制重新转换"""
        data_source, xlsx_path = sample_xlsx
        pq_dir = temp_dir / "parquet"
        pq_dir.mkdir()

        with patch('scripts.etl.config.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.fill_parquet_cache.PARQUET_DATA_DIR', pq_dir):
            from scripts.etl.fill_parquet_cache import fill_parquet_cache

            # 第一次运行
            fill_parquet_cache(data_source, "shop")

            # 第二次运行（force=True，应重新转换）
            converted, skipped, _ = fill_parquet_cache(data_source, "shop", force=True)
            assert converted == 1
            assert skipped == 0

    def test_fill_parquet_cache_no_order_id(self, temp_dir):
        """测试错误处理：无 order_id 列的文件"""
        data_source = temp_dir / "source"
        data_source.mkdir()
        xlsx_path = data_source / "bad_file.xlsx"
        df = pd.DataFrame({
            '无关列': ['a', 'b'],
        })
        df.to_excel(xlsx_path, index=False, engine='openpyxl')

        pq_dir = temp_dir / "parquet"
        pq_dir.mkdir()

        with patch('scripts.etl.config.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.fill_parquet_cache.PARQUET_DATA_DIR', pq_dir):
            from scripts.etl.fill_parquet_cache import fill_parquet_cache

            converted, _, errors = fill_parquet_cache(data_source, "shop")
            assert converted == 0
            assert errors == 1

    def test_fill_parquet_cache_cleans_tmp_on_start(self, temp_dir, sample_xlsx):
        """测试启动时清理残留的 .parquet.tmp 文件"""
        data_source, xlsx_path = sample_xlsx
        pq_dir = temp_dir / "parquet"
        pq_dir.mkdir()

        # 创建残留的 .tmp 文件
        shop_dir = pq_dir / "shop"
        shop_dir.mkdir()
        (shop_dir / "test_order.parquet.tmp").touch()
        assert len(list(shop_dir.glob("*.parquet.tmp"))) == 1

        with patch('scripts.etl.config.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.fill_parquet_cache.PARQUET_DATA_DIR', pq_dir):
            from scripts.etl.fill_parquet_cache import fill_parquet_cache

            fill_parquet_cache(data_source, "shop")

            # 验证 .tmp 文件被清理
            tmp_files = list(shop_dir.glob("*.parquet.tmp"))
            assert len(tmp_files) == 0

            # 验证 Parquet 文件正常生成
            pq_files = list(shop_dir.glob("*.parquet"))
            assert len(pq_files) == 1

    def test_fill_parquet_cache_updates_processed_files(self, temp_dir, sample_xlsx):
        """测试 processed_files 更新"""
        data_source, xlsx_path = sample_xlsx
        pq_dir = temp_dir / "parquet"
        pq_dir.mkdir()
        processed_dir = temp_dir / "processed"
        processed_dir.mkdir()

        with patch('scripts.etl.config.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.config.PROCESSED_DATA_DIR', processed_dir), \
             patch('scripts.etl.fill_parquet_cache.PARQUET_DATA_DIR', pq_dir), \
             patch('scripts.etl.fill_parquet_cache._save_processed_files') as mock_save:
            from scripts.etl.fill_parquet_cache import fill_parquet_cache

            fill_parquet_cache(data_source, "shop")

            # 验证 _save_processed_files 被调用
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            assert call_args[0][0] == "shop"
            assert len(call_args[0][1]) == 1


class TestSaveParquetCacheAtomic:
    """_save_parquet_cache 原子写入测试"""

    def test_atomic_write_success(self, tmp_path):
        """测试正常原子写入"""
        from scripts.etl.ingest import _save_parquet_cache

        pq_dir = tmp_path / "parquet" / "shop"
        pq_dir.mkdir(parents=True)

        df = pd.DataFrame({'col1': [1, 2], 'col2': ['a', 'b']})
        xlsx_path = tmp_path / "test.xlsx"
        xlsx_path.touch()

        with patch('scripts.etl.ingest.PARQUET_DATA_DIR', tmp_path / "parquet"):
            _save_parquet_cache(df, xlsx_path, "shop")

        # 验证 Parquet 文件存在
        pq_files = list(pq_dir.glob("*.parquet"))
        assert len(pq_files) == 1
        assert pq_files[0].name == "test.parquet"

        # 验证没有 .tmp 文件残留
        tmp_files = list(pq_dir.glob("*.parquet.tmp"))
        assert len(tmp_files) == 0

    def test_atomic_write_failure_cleanup(self, tmp_path):
        """测试原子写入失败时清理 .tmp 文件"""
        from scripts.etl.ingest import _save_parquet_cache

        pq_dir = tmp_path / "parquet" / "shop"
        pq_dir.mkdir(parents=True)

        df = pd.DataFrame({'col1': [1, 2]})
        xlsx_path = tmp_path / "test.xlsx"
        xlsx_path.touch()

        # 模拟 to_parquet 失败
        with patch('scripts.etl.ingest.PARQUET_DATA_DIR', tmp_path / "parquet"), \
             patch.object(pd.DataFrame, 'to_parquet', side_effect=Exception("写入失败")):
            _save_parquet_cache(df, xlsx_path, "shop")

        # 验证没有 Parquet 文件
        pq_files = list(pq_dir.glob("*.parquet"))
        assert len(pq_files) == 0

        # 验证 .tmp 文件被清理
        tmp_files = list(pq_dir.glob("*.parquet.tmp"))
        assert len(tmp_files) == 0


class TestIngestParquetIntegration:
    """集成测试：fill 脚本产出的 parquet 能被 ingest.py 正确读取"""

    def test_parquet_readable_by_ingest(self, tmp_path):
        """测试 fill 脚本生成的 parquet 能被 load_data_files 正确读取"""
        # 创建测试 xlsx
        data_source = tmp_path / "source"
        data_source.mkdir()
        xlsx_path = data_source / "test_order.xlsx"
        df_original = pd.DataFrame({
            '订单编号': ['ORD001', 'ORD002'],
            '用户ID': ['U001', 'U002'],
            '下单时间': ['2026-01-01 10:00:00', '2026-01-02 11:00:00'],
            '实付金额': [100.0, 200.0],
        })
        df_original.to_excel(xlsx_path, index=False, engine='openpyxl')

        # 创建 Parquet 缓存目录
        pq_dir = tmp_path / "parquet" / "shop"
        pq_dir.mkdir(parents=True)

        # 用 fill 脚本的逻辑生成 Parquet
        from scripts.etl.ingest import rename_columns

        df = pd.read_excel(xlsx_path, engine='openpyxl', header=0)
        df.columns = [c.strip() if isinstance(c, str) else c for c in df.columns]
        df = rename_columns(df)
        if 'order_time' in df.columns:
            df['order_time'] = pd.to_datetime(df['order_time'], errors='coerce')
            df['year'] = df['order_time'].dt.year
            df['month'] = df['order_time'].dt.month

        pq_path = pq_dir / "test_order.parquet"
        df.to_parquet(pq_path, index=False)

        # 用 ingest.py 的逻辑读取 Parquet
        df_read = pd.read_parquet(pq_path)
        df_read = rename_columns(df_read)

        # 验证列名正确
        assert 'order_id' in df_read.columns
        assert 'user_id' in df_read.columns

        # 验证数据行数
        assert len(df_read) == 2

        # 验证数据内容
        assert df_read['order_id'].tolist() == ['ORD001', 'ORD002']
