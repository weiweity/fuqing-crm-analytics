"""
Sprint 109 L4.7 实战 fix 模式 regression test.

修 _file_changed mtime 不变短路 bug: mtime 不变 + 内容变 → 必须 hash 比对.
触发场景: 用户 cp -p / Finder 替换 xlsx 保持 mtime 不变, 内容变了.

跟 Sprint 90 / Sprint 93 / Sprint 93.1 / Sprint 93.3 / Sprint 107 / Sprint 108
L4.7 实战 fix 模式一致 (1 行修 + 0 抽象 + regression test).
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, '/Users/hutou/Desktop/fuqin-date/fuqing-crm-analytics')

from scripts.etl.ingest import _file_changed


def _make_xlsx(tmp_dir: Path, content: bytes, mtime: float) -> Path:
    """写测试 xlsx + 设 mtime."""
    p = tmp_dir / "test.xlsx"
    p.write_bytes(content)
    os.utime(p, (mtime, mtime))
    return p


def test_file_changed_mtime_unchanged_content_changed_returns_true():
    """Sprint 109 真治本: mtime 不变 + 内容变 → 必须 hash 比对, 返回 True."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        xlsx = _make_xlsx(tmp_dir, b'content v1', 1000000000.0)

        # 模拟 tracker 已记录旧内容
        processed = {
            str(xlsx.relative_to(tmp_dir)): {
                'mtime': 1000000000.0,
                'hash': _get_file_hash(xlsx),
                'cold_start_marked': False,
            },
        }

        # 修改内容但保持 mtime (cp -p 模式)
        xlsx.write_bytes(b'content v2 - totally different')
        os.utime(xlsx, (1000000000.0, 1000000000.0))

        result = _file_changed(
            xlsx, processed, tmp_dir, {xlsx.stem: str(xlsx.relative_to(tmp_dir))},
        )
        assert result is True, (
            "Sprint 109 真治本: mtime 不变 + 内容变 → 必须返回 True "
            "(新修法: 算 hash 比对, 不短路跳过)"
        )


def test_file_changed_mtime_unchanged_content_unchanged_returns_false():
    """95% 场景优化保留: mtime 不变 + 内容不变 → 短路跳过, 返回 False."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        xlsx = _make_xlsx(tmp_dir, b'content v1', 1000000000.0)

        processed = {
            str(xlsx.relative_to(tmp_dir)): {
                'mtime': 1000000000.0,
                'hash': _get_file_hash(xlsx),
                'cold_start_marked': False,
            },
        }

        # 内容不变, mtime 不变
        result = _file_changed(
            xlsx, processed, tmp_dir, {xlsx.stem: str(xlsx.relative_to(tmp_dir))},
        )
        assert result is False, (
            "95% 场景优化保留: mtime 不变 + 内容不变 → 应该返回 False "
            "(优化: 不算 hash, 短路跳过)"
        )


def test_file_changed_mtime_changed_returns_true():
    """正常情况: mtime 变了 → 返回 True (强制重读)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        xlsx = _make_xlsx(tmp_dir, b'content v1', 1000000000.0)

        processed = {
            str(xlsx.relative_to(tmp_dir)): {
                'mtime': 999999999.0,  # 旧 mtime
                'hash': 'old_hash',
                'cold_start_marked': False,
            },
        }

        # mtime 变了
        os.utime(xlsx, (2000000000.0, 2000000000.0))

        result = _file_changed(
            xlsx, processed, tmp_dir, {xlsx.stem: str(xlsx.relative_to(tmp_dir))},
        )
        assert result is True


def test_skip_mtime_check_env_var_disables_new_logic():
    """ETL_SKIP_MTIME_CHECK_HASH=1 → 走老逻辑 (mtime 短路, 兼容测试 / 老跑批)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        xlsx = _make_xlsx(tmp_dir, b'content v1', 1000000000.0)

        processed = {
            str(xlsx.relative_to(tmp_dir)): {
                'mtime': 1000000000.0,
                'hash': _get_file_hash(xlsx),
                'cold_start_marked': False,
            },
        }

        xlsx.write_bytes(b'content v2 - changed')
        os.utime(xlsx, (1000000000.0, 1000000000.0))

        old_env = os.environ.get('ETL_SKIP_MTIME_CHECK_HASH')
        os.environ['ETL_SKIP_MTIME_CHECK_HASH'] = '1'
        try:
            result = _file_changed(
                xlsx, processed, tmp_dir, {xlsx.stem: str(xlsx.relative_to(tmp_dir))},
            )
            assert result is False, (
                "ETL_SKIP_MTIME_CHECK_HASH=1 走老逻辑: mtime 不变短路返回 False (兼容老跑批)"
            )
        finally:
            if old_env is None:
                os.environ.pop('ETL_SKIP_MTIME_CHECK_HASH', None)
            else:
                os.environ['ETL_SKIP_MTIME_CHECK_HASH'] = old_env


def _get_file_hash(file_path):
    """延迟 import 避免循环引用."""
    from scripts.etl.config import _get_file_hash as _h
    return _h(file_path)
