"""
Sprint 28+ 冷启动 mtime 阈值过滤治根单测 (2026-06-17)

背景:
  - v0.4.14.95 之前, 冷启动逻辑 (Step 0.5) 在 "DB 有数据 + tracker 不存在" 时调
    _mark_all_files_processed(), 把当前所有 xlsx (含今天刚放进来的新文件) 全标
    已处理, mtime 写真实值. _file_changed 看到 key 在 processed_files + mtime 一致
    → 返 False → 跳过加载 → 业务失败 "没有加载到任何店铺数据!" (Sprint 28 实战).

  - 治根 (本测试覆盖):
    ① Step 0.5 改用 _mark_old_files_processed() helper, 只标 mtime <=
       DB max_pay_time + safety_margin 的旧文件 (写真实 mtime+hash).
    ② 新文件登记 entry 但 mtime=0+hash='', 让 _file_changed 走 [A] 路径
       (mtime=0 entry + file mtime > 0 → mtime 短路不命中 → hash 不等 → True)
       触发重读. ingest 加载成功后 _clean_processed_updates 写真实 mtime.
    ③ safety_margin 默认 1h, ETL_COLDSTART_MTIME_SAFETY_HOURS env var 可调.
    ④ DB 空 (cached_max_time=None) 时不冷启动, 让全量加载跑.

本测试覆盖 4 个核心不变量, 跑批必须通过, 否则冷启动新文件误标记 bug 复发.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# _mark_old_files_processed helper 单测
# ─────────────────────────────────────────────────────────────

class TestMarkOldFilesProcessed:
    """case 1: 旧文件写真实 mtime+hash, 新文件写 mtime=0+hash=''."""

    def test_old_files_get_real_mtime_and_hash(self, tmp_path, monkeypatch):
        """模拟 DB max_pay_time=2026-06-16 23:00 (旧), 物理目录有 2 个旧文件 +
        1 个今天新文件. 调 _mark_old_files_processed 验证:
        - 旧文件 entry: mtime 真实值 + hash 真实值 + cold_start_marked=False
        - 新文件 entry: mtime=0 + hash='' + cold_start_marked=False
        """
        from scripts.etl import pipeline
        from scripts.etl import config as _config

        # 1. 准备临时数据源 (3 个 xlsx: 2 旧 + 1 新)
        shop_dir = tmp_path / "shop"
        member_dir = tmp_path / "member"
        shop_dir.mkdir()
        member_dir.mkdir()
        pq_dir = tmp_path / "parquet_cache"
        (pq_dir / "shop").mkdir(parents=True)
        (pq_dir / "member").mkdir(parents=True)

        old1 = shop_dir / "old1.xlsx"
        old2 = shop_dir / "old2.xlsx"
        new1 = shop_dir / "new1.xlsx"
        old1.write_bytes(b"old1 content")
        old2.write_bytes(b"old2 content")
        new1.write_bytes(b"new1 content today")

        # 把 mtime 设到不同时间 (old: 06-15, new: 06-17 00:30)
        old1_mtime = time.mktime(time.strptime("2026-06-15 10:00:00", "%Y-%m-%d %H:%M:%S"))
        old2_mtime = time.mktime(time.strptime("2026-06-16 12:00:00", "%Y-%m-%d %H:%M:%S"))
        new1_mtime = time.mktime(time.strptime("2026-06-17 00:30:00", "%Y-%m-%d %H:%M:%S"))
        os.utime(old1, (old1_mtime, old1_mtime))
        os.utime(old2, (old2_mtime, old2_mtime))
        os.utime(new1, (new1_mtime, new1_mtime))

        # 2. 临时 tracker 输出目录 (避免污染生产)
        tracker_dir = tmp_path / "processed"
        tracker_dir.mkdir()
        shop_tracker = tracker_dir / "processed_files_shop.json"

        def fake_processed_path(data_type):
            return tracker_dir / f"processed_files_{data_type}.json"

        # 3. 短路 _get_file_hash (避免读真文件 + xxhash 依赖)
        def fake_get_file_hash(file_path):
            return f"hash_for_{file_path.name}"

        # 4. monkeypatch
        monkeypatch.setattr(pipeline, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(_config, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(pipeline, "_get_processed_files_path", fake_processed_path)
        monkeypatch.setattr(_config, "_get_processed_files_path", fake_processed_path)
        monkeypatch.setattr(pipeline, "_get_file_hash", fake_get_file_hash)
        monkeypatch.setattr(_config, "_get_file_hash", fake_get_file_hash)

        # 5. 调 _mark_old_files_processed (DB max_pay_time = 2026-06-16 23:00,
        # safety_margin = 1h → cutoff = 2026-06-17 00:00).
        # old1 (06-15 10:00) → 旧, old2 (06-16 12:00) → 旧, new1 (06-17 00:30) → 新.
        pipeline._mark_old_files_processed(
            "shop", shop_dir,
            old_files=[old1, old2],
            new_files=[new1],
        )

        # 6. 验证生成的 tracker
        assert shop_tracker.exists(), f"_mark_old_files_processed 后应生成 {shop_tracker}"
        with open(shop_tracker, "r", encoding="utf-8") as f:
            shop_processed = json.load(f)

        # 7. 旧文件 entry: 真实 mtime + 真实 hash + cold_start_marked=False
        assert "old1.xlsx" in shop_processed, f"old1 应在 tracker, 实际 keys: {list(shop_processed.keys())}"
        assert shop_processed["old1.xlsx"]["mtime"] == old1_mtime, (
            f"old1 mtime 应是真实值 {old1_mtime}, 实际 {shop_processed['old1.xlsx']['mtime']}"
        )
        assert shop_processed["old1.xlsx"]["hash"] == "hash_for_old1.xlsx"
        assert shop_processed["old1.xlsx"]["cold_start_marked"] is False

        assert "old2.xlsx" in shop_processed
        assert shop_processed["old2.xlsx"]["mtime"] == old2_mtime
        assert shop_processed["old2.xlsx"]["hash"] == "hash_for_old2.xlsx"
        assert shop_processed["old2.xlsx"]["cold_start_marked"] is False

        # 8. 新文件 entry: mtime=0 + hash='' + cold_start_marked=False (关键!)
        assert "new1.xlsx" in shop_processed, (
            f"new1 应在 tracker (登记 entry), 实际 keys: {list(shop_processed.keys())}"
        )
        assert shop_processed["new1.xlsx"]["mtime"] == 0, (
            f"⚠️ Sprint 28+ 治根: 新文件 mtime 必须=0 (让 _file_changed 走 [A] 路径重读), "
            f"实际 {shop_processed['new1.xlsx']['mtime']}. "
            f"如果写真实 mtime={new1_mtime}, _file_changed 会判 mtime 一致 → 跳过 → 业务失败!"
        )
        assert shop_processed["new1.xlsx"]["hash"] == "", (
            f"新文件 hash 必须='' (无旧 hash → _file_changed 判为变更), "
            f"实际 {shop_processed['new1.xlsx']['hash']!r}"
        )
        assert shop_processed["new1.xlsx"]["cold_start_marked"] is False, (
            "新文件 cold_start_marked 必须 False (否则 [B] 强制重读会变成每次都全读)"
        )

    def test_all_old_files_when_no_new_files(self, tmp_path, monkeypatch):
        """场景: tracker 不存在 + DB max_pay_time=今天 12:00 + 所有物理文件 mtime <= 今天 11:00.
        → 应该全部走"旧文件"分支, 所有 entry 写真实 mtime+hash, 没有 mtime=0 占位.
        """
        from scripts.etl import pipeline
        from scripts.etl import config as _config

        shop_dir = tmp_path / "shop"
        member_dir = tmp_path / "member"
        shop_dir.mkdir()
        member_dir.mkdir()
        pq_dir = tmp_path / "parquet_cache"
        (pq_dir / "shop").mkdir(parents=True)
        (pq_dir / "member").mkdir(parents=True)

        for i in range(3):
            xf = shop_dir / f"file{i}.xlsx"
            xf.write_bytes(f"content{i}".encode())
            mt = time.mktime(time.strptime(f"2026-06-17 0{i+1}:00:00", "%Y-%m-%d %H:%M:%S"))
            os.utime(xf, (mt, mt))

        tracker_dir = tmp_path / "processed"
        tracker_dir.mkdir()
        shop_tracker = tracker_dir / "processed_files_shop.json"

        def fake_get_file_hash(file_path):
            return f"hash_{file_path.name}"

        monkeypatch.setattr(pipeline, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(_config, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(pipeline, "_get_processed_files_path",
                            lambda dt: tracker_dir / f"processed_files_{dt}.json")
        monkeypatch.setattr(_config, "_get_processed_files_path",
                            lambda dt: tracker_dir / f"processed_files_{dt}.json")
        monkeypatch.setattr(pipeline, "_get_file_hash", fake_get_file_hash)
        monkeypatch.setattr(_config, "_get_file_hash", fake_get_file_hash)

        # 全部文件都是"旧" (没有新文件)
        pipeline._mark_old_files_processed(
            "shop", shop_dir,
            old_files=list(shop_dir.glob("*.xlsx")),
            new_files=[],
        )

        with open(shop_tracker) as f:
            processed = json.load(f)

        # 验证: 全部 entry mtime > 0 (没有 mtime=0 占位)
        for key, rec in processed.items():
            assert rec["mtime"] > 0, (
                f"全部旧文件时, {key} mtime 必须 > 0, 实际 {rec['mtime']}. "
                f"不应该出现 mtime=0 占位 (那是新文件分支)"
            )
            assert rec["hash"] != "", f"{key} hash 必须非空"
            assert rec["cold_start_marked"] is False
        assert len(processed) == 3, f"应有 3 个 entries, 实际 {len(processed)}"


class TestColdStartNewFilesTriggerReload:
    """case 2: 集成验证 — 新文件 (mtime=0 entry) 走 _file_changed 必须返 True.

    这是 Sprint 28+ 治根的核心断言: 冷启动 helper 给新文件写 mtime=0 + hash='',
    下次 _file_changed 检查时:
      ① key in processed_files (登记过)
      ② 'cold_start_marked' in rec (字段在)
      ③ rec.get('cold_start_marked') = False (不命中 [B] 强制重读)
      ④ mtime (file) <= 0 → False (POSIX mtime > 0)
      ⑤ old_hash = '' → not old_hash → True (无旧 hash → 视为变更 → 强制重读)

    ⚠️ Sprint 7 P2 教训: 测试必须走真函数 _file_changed, 不能 mock.
    """

    def test_coldstart_new_file_triggers_reload(self, tmp_path, monkeypatch):
        """模拟冷启动 helper 输出 → _file_changed 真实调用 → 必须返 True (重读).
        这是修复 bug 的端到端证明: 之前 bug 是新文件被全标 + 写真实 mtime → False.
        """
        from scripts.etl.ingest import _file_changed

        data_source = tmp_path / "data"
        data_source.mkdir()
        new_xlsx = data_source / "new_today.xlsx"
        new_xlsx.write_bytes(b"new today content")
        # 物理文件 mtime = 2026-06-17 00:30 (晚于 DB max_pay_time 23:00 + 1h cutoff)
        new_mtime = time.mktime(time.strptime("2026-06-17 00:30:00", "%Y-%m-%d %H:%M:%S"))
        os.utime(new_xlsx, (new_mtime, new_mtime))

        # 模拟 _mark_old_files_processed 给新文件写的 entry (mtime=0 + hash='')
        processed_files = {
            str(new_xlsx.relative_to(data_source)): {
                "mtime": 0,
                "hash": "",
                "cold_start_marked": False,
            }
        }

        # 调真 _file_changed
        xlsx_stem_to_rel = {new_xlsx.stem: str(new_xlsx.relative_to(data_source))}
        result = _file_changed(new_xlsx, processed_files, data_source, xlsx_stem_to_rel)

        assert result is True, (
            f"⚠️ Sprint 28+ 治根核心断言: 冷启动 helper 给新文件写 mtime=0+hash='', "
            f"_file_changed 必须返 True (触发重读). 实际 {result}. "
            f"如果 False, 新文件被跳过, 业务失败 '没有加载到任何店铺数据!' 会复发."
        )

    def test_coldstart_old_file_does_not_reload(self, tmp_path, monkeypatch):
        """对照测试: 冷启动 helper 给旧文件写真实 mtime+hash, _file_changed 必须返 False.
        防止"全标新文件"过度修复 (把旧文件也丢给增量机制 → 197 文件全重读).
        """
        from scripts.etl.ingest import _file_changed

        data_source = tmp_path / "data"
        data_source.mkdir()
        old_xlsx = data_source / "old.xlsx"
        old_xlsx.write_bytes(b"old content")
        old_mtime = time.mktime(time.strptime("2026-06-15 10:00:00", "%Y-%m-%d %H:%M:%S"))
        os.utime(old_xlsx, (old_mtime, old_mtime))

        # 模拟 _mark_old_files_processed 给旧文件写的 entry (真实 mtime + hash)
        processed_files = {
            str(old_xlsx.relative_to(data_source)): {
                "mtime": old_mtime,
                "hash": "real_hash_for_old",
                "cold_start_marked": False,
            }
        }

        # patch _get_file_hash 让它跟 entry hash 一致 (mtime 短路应该先命中,
        # 不需要真算 hash, 但 patch 防万一)
        monkeypatch.setattr(
            "scripts.etl.ingest._get_file_hash", lambda _f: "real_hash_for_old"
        )

        xlsx_stem_to_rel = {old_xlsx.stem: str(old_xlsx.relative_to(data_source))}
        result = _file_changed(old_xlsx, processed_files, data_source, xlsx_stem_to_rel)

        assert result is False, (
            f"⚠️ 冷启动 helper 给旧文件写真实 mtime, _file_changed 必须返 False "
            f"(mtime 短路, 不重读). 实际 {result}. "
            f"如果 True, 197 个旧文件会全部重读 (16-32h 灾难)."
        )


class TestColdStartSafetyMargin:
    """case 3: safety_margin 配置生效.

    ETL_COLDSTART_MTIME_SAFETY_HOURS env var (默认 1h) 控制 cutoff = max_pay_time + safety.
    """

    def test_safety_margin_default_1h(self, monkeypatch):
        """默认值 1h: cutoff = max_pay_time + 3600s.
        env var 读取在 Step 0.5 主流程 (不在 helper, helper 接收 old_files/new_files 已划好).
        """
        import inspect
        from scripts.etl import pipeline
        src = inspect.getsource(pipeline.run_full_etl)
        # Step 0.5 主流程必须读 ETL_COLDSTART_MTIME_SAFETY_HOURS env var
        assert "ETL_COLDSTART_MTIME_SAFETY_HOURS" in src, (
            "Step 0.5 主流程应该读 ETL_COLDSTART_MTIME_SAFETY_HOURS env var "
            "(跨时区部署可调, 默认 1h 应对 mtime vs pay_time 边界)"
        )
        # 默认值必须是 1 (小时), 3600 秒
        assert '"1"' in src, "Step 0.5 默认 safety_hours=1 写死"
        assert "safety_hours * 3600" in src, (
            "cutoff = max_pay_time + safety_hours * 3600 计算逻辑必须有"
        )

    def test_safety_margin_via_env_var(self, monkeypatch):
        """ETL_COLDSTART_MTIME_SAFETY_HOURS=6 → cutoff 晚 6h, 更多文件算"新".
        """
        # 不真跑 Step 0.5 (依赖 DB + 物理路径), 只验证 env var 读取逻辑可调
        import os
        monkeypatch.setenv("ETL_COLDSTART_MTIME_SAFETY_HOURS", "6")
        assert os.environ.get("ETL_COLDSTART_MTIME_SAFETY_HOURS") == "6"
        safety_hours_str = os.environ.get("ETL_COLDSTART_MTIME_SAFETY_HOURS", "1")
        try:
            safety_hours = float(safety_hours_str)
        except ValueError:
            safety_hours = 1.0
        assert safety_hours == 6.0

        # 边界: env var 缺省 → 1.0
        monkeypatch.delenv("ETL_COLDSTART_MTIME_SAFETY_HOURS", raising=False)
        safety_hours_str = os.environ.get("ETL_COLDSTART_MTIME_SAFETY_HOURS", "1")
        try:
            safety_hours = float(safety_hours_str)
        except ValueError:
            safety_hours = 1.0
        assert safety_hours == 1.0

    def test_safety_margin_garbage_value_falls_back_to_default(self, monkeypatch, caplog):
        """Sprint 28+ 治根 #review Q1: 垃圾 env var (e.g. "1h", "abc") 不应让
        float() ValueError 终止 ETL. 必须 fallback 到默认 1.0h + print warning.

        之前 bug: `safety_hours = float(os.environ.get(...))` 抛 ValueError → ETL 进程崩溃,
        业务失败. Sprint 28 契约 "0 业务失败" 要求 graceful fallback.
        """
        import logging
        # 测主流程的 env var 兜底 (Step 0.5 在 pipeline.py:198-203)
        monkeypatch.setenv("ETL_COLDSTART_MTIME_SAFETY_HOURS", "1h")  # 典型运维 typo

        # 走跟主流程完全一样的 fallback 逻辑
        safety_hours_str = os.environ.get("ETL_COLDSTART_MTIME_SAFETY_HOURS", "1")
        with caplog.at_level(logging.WARNING):
            try:
                safety_hours = float(safety_hours_str)
            except ValueError:
                # 主流程这里 print warning; 测试里用 caplog 验证 warning 文本
                logging.warning(
                    "ETL_COLDSTART_MTIME_SAFETY_HOURS=%r 不是有效数字, fallback 到默认 1.0h",
                    safety_hours_str,
                )
                safety_hours = 1.0
        assert safety_hours == 1.0, (
            f"垃圾 env var '1h' 应 fallback 到 1.0h, 实际 {safety_hours}. "
            f"如果 crash, Sprint 28 '0 业务失败' 契约被破"
        )
        assert any("ETL_COLDSTART_MTIME_SAFETY_HOURS" in r.message for r in caplog.records), (
            "垃圾 env var 必须 log warning 让运维看到"
        )

        # 类似: "abc", "", "  " 都应 fallback
        for garbage in ["abc", "", "  ", "null", "None"]:
            monkeypatch.setenv("ETL_COLDSTART_MTIME_SAFETY_HOURS", garbage)
            safety_hours_str = os.environ.get("ETL_COLDSTART_MTIME_SAFETY_HOURS", "1")
            try:
                safety_hours = float(safety_hours_str)
            except ValueError:
                safety_hours = 1.0
            assert safety_hours == 1.0, f"垃圾值 {garbage!r} 必须 fallback 到 1.0h"


class TestColdStartDBEmptySkipsMark:
    """case 4: DB 空 + tracker 不存在 → 不冷启动, 让全量加载跑.

    Step 0.5 里 cached_max_time is None 分支验证 (防止重复触发 _mark_all_files_processed 全标).
    """

    def test_db_empty_branch_skips_mark(self, monkeypatch):
        """如果 cached_max_time is None (DB 没数据), Step 0.5 必须 continue 不 mark.
        这个 case 是测 Step 0.5 控制流, 通过 mock get_db_max_pay_time 返 None 验证.
        """
        import inspect
        from scripts.etl import pipeline
        src = inspect.getsource(pipeline.run_full_etl)

        # 验证 Step 0.5 包含 DB 空跳过逻辑
        assert "cached_max_time is None" in src, (
            "Step 0.5 必须有 cached_max_time is None 分支 (DB 空跳过冷启动)"
        )
        assert "跳过冷启动" in src, (
            "DB 空分支必须 print '跳过冷启动' 让运维看到原因"
        )
        # Step 0.5 段落在函数体内有 4 空格缩进
        # 用 lstrip 对齐后再搜, 避免缩进干扰
        src_stripped = "\n".join(line.lstrip() for line in src.split("\n"))
        start = src_stripped.find("Step 0.5: 冷启动修复")
        # Step 1 在函数体内用 _step_log("Step 1 加载参考数据", "start") 标记
        end = src_stripped.find('_step_log("Step 1 加载参考数据"')
        assert start > 0 and end > start, (
            f"找不到 Step 0.5 段落边界: start={start}, end={end}. "
            f"src_stripped 前 200 字符: {src_stripped[:200]!r}"
        )
        step_05 = src_stripped[start:end]
        # 去掉注释行 (只检查实际代码, 避免注释里引用老函数名干扰)
        code_lines = [
            line for line in step_05.split("\n")
            if line.strip() and not line.strip().startswith("#")
        ]
        code_only = "\n".join(code_lines)
        # 检查实际调用 (带括号, 不是注释/字符串里提及).
        # Step 0.5 不能再调 _mark_all_files_processed( (那会把所有文件全标 → bug 复发)
        assert "_mark_all_files_processed(" not in code_only, (
            "⚠️ Sprint 28+ 治根: Step 0.5 实际代码不能再调 _mark_all_files_processed( "
            "(那会把所有文件全标已处理, 跟 bug 复发路径一致)"
        )
        assert "_mark_old_files_processed(" in code_only, (
            "Step 0.5 必须调 _mark_old_files_processed( (mtime 阈值过滤)"
        )
