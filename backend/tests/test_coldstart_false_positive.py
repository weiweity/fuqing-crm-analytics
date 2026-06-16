"""
Sprint 24 cold-start false-positive 修复单测 (2026-06-16)

背景:
  - v0.4.14.60 之前 _mark_all_files_processed 写入的 entry 没有
    cold_start_marked 标记, 增量跑批第二次走 _file_changed 检查, mtime/hash
    都对得上 → 误判"已处理" → 跳过 108 个 xlsx 重读 → 假阳性冷启动
    (DB 已经有数据, 但 processed_files tracker 显示"全处理完", 增量什么都不做).

  - 修复 (Sprint 24 P0-1):
    ① _mark_all_files_processed 写入 entry 时加 cold_start_marked=False + marked_at
       (Sprint 24 治根: 必须写 False 而非 True, 否则 ingest._file_changed 路径 [B]
        rec.get('cold_start_marked') → True 强制重读, 197 个文件 16-32h 灾难)
    ② _file_changed 路径 [A]: key not in processed_files → 强制重读
       (真"需重读"由 [A] 触发, 是 O2 增量 entry 模式下的新文件)
    ③ _file_changed 路径 [B]: rec.get('cold_start_marked') True → 重读
       (冷启动时 _mark_all_files_processed 写 False, [B] 不会触发)
    ④ Step 4.5 upsert 成功后, _clean_processed_updates 保留 cold_start_marked 字段
       (置 False, 不 del — 避免 _file_changed ① 'cold_start_marked' not in rec
        误判为老格式导致死循环), 追加 last_processed_at 时间戳, 让下次增量走
       正常的 mtime/hash 比对

本测试覆盖 5 个核心不变量, 跑批必须通过, 否则冷启动假阳性会复发.
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT))


# ─────────────────────────────────────────────────────────────
# 核心函数直接单测 (module-level, 无 IO, 极快)
# ─────────────────────────────────────────────────────────────

class TestColdStartMarkedFilesAreReloaded:
    """case 1: cold_start_marked=True 的 entry 必须被 _file_changed 视为变更."""

    def test_cold_start_marked_files_are_reloaded(self, tmp_path, monkeypatch):
        """模拟一个 entry {mtime, hash, cold_start_marked=True}, 调 _file_changed
        断言返回 True (强制重载, 不允许走 mtime/hash 短路逻辑).

        Sprint 24 技术债 #2: 直接调真函数 _file_changed (module-level).
        """
        from scripts.etl.ingest import _file_changed

        # 构造一个真实的 xlsx 文件
        data_source = tmp_path / "data"
        data_source.mkdir()
        xlsx_path = data_source / "test.xlsx"
        xlsx_path.write_bytes(b"fake xlsx content for cold start test")

        # entry 含 cold_start_marked=True, mtime 与文件一致
        processed_files = {
            str(xlsx_path.relative_to(data_source)): {
                "mtime": xlsx_path.stat().st_mtime,  # 与真实 mtime 一致
                "hash": "fakehash",
                "cold_start_marked": True,
                "marked_at": time.time(),
            }
        }

        # patch _get_file_hash 避免真算 hash (本测试核心是 cold_start 标志位短路,
        # 让 hash 跟 entry 一致, 排除 hash 干扰)
        monkeypatch.setattr(
            "scripts.etl.ingest._get_file_hash", lambda _f: "fakehash"
        )

        # 直接调真 _file_changed — 走 ③ cold_start_marked=True 路径返 True
        xlsx_stem_to_rel = {xlsx_path.stem: str(xlsx_path.relative_to(data_source))}
        result = _file_changed(xlsx_path, processed_files, data_source, xlsx_stem_to_rel)
        assert result is True, (
            "cold_start_marked=True 的 entry 应被 _file_changed 识别为'未真正加载', "
            "触发强制重载 (避免冷启动假阳性). 实际: {result}"
        )


class TestOldFormatEntryWithoutColdStartFlagIsReloaded:
    """case 1.5: Option B 向后兼容 — 老格式 entry (无 cold_start_marked 字段)
    必须被识别为'未真正加载', 触发一次性强制重载 (迁移路径).

    背景: 部署 Sprint 24 P0-1 修复前, 现有 tracker 条目都是 v0.4.14.60 的
    {mtime, hash} 格式, 没有 cold_start_marked 字段. 用户的 6/15 数据
    已经被这种老格式 entry 误标, 部署后必须能自动重载, 否则 dashboard
    永远 0.
    """

    def test_old_format_entry_forces_reload(self, tmp_path, monkeypatch):
        """构造一个 {mtime, hash} 老格式 entry (无 cold_start_marked),
        mtime 与文件一致 → 正常流程会判定为未变,
        但 Option B 修复必须识别为'老格式'强制重载 (字段缺失短路).

        Sprint 24 技术债 #2: 直接调真函数 _file_changed 验证.
        """
        from scripts.etl.ingest import _file_changed

        data_source = tmp_path / "data"
        data_source.mkdir()
        xlsx_path = data_source / "old_format.xlsx"
        xlsx_path.write_bytes(b"old format content")

        # 老格式 entry: 只有 mtime + hash, 没有 cold_start_marked
        current_mtime = xlsx_path.stat().st_mtime
        processed_files = {
            str(xlsx_path.relative_to(data_source)): {
                "mtime": current_mtime,  # 与真实 mtime 一致
                "hash": "old_hash_will_be_recomputed",
                # 注意: 没有 cold_start_marked 字段 ← 这是关键
            }
        }

        # 验证 Option B 判定: 'cold_start_marked' not in rec → 强制重载
        for key, rec in processed_files.items():
            assert "cold_start_marked" not in rec, (
                f"本测试用例前提: {key} 不应有 cold_start_marked 字段"
            )

        # 直接调真函数 — 缺字段应触发 ② 路径返 True
        xlsx_stem_to_rel = {xlsx_path.stem: str(xlsx_path.relative_to(data_source))}
        result = _file_changed(xlsx_path, processed_files, data_source, xlsx_stem_to_rel)
        assert result is True, (
            "老格式 entry (缺 cold_start_marked 字段) 必须被 _file_changed "
            "识别为'老格式'强制重载 (Sprint 24 Option B 向后兼容). 实际: {result}"
        )

    def test_loaded_entry_not_reloaded_after_processing(self):
        """加载成功后的 entry (cold_start_marked 字段被 _clean_processed_updates
        置 False + last_processed_at 已写入) → 下次增量必须走 mtime/hash
        正常流程, 不再触发强制重载.

        ⚠️ 这是 QA 发现的死循环 bug 的回归测试:
        之前实现是 del cold_start_marked 字段, 导致加载成功后 entry 缺字段,
        _file_changed ① 'cold_start_marked' not in rec → True, 每次都重读.
        现在改成置 False (字段保留), 字段存在 → 不命中 ①.
        """
        from scripts.etl.ingest import _clean_processed_updates

        # 模拟冷启动登记 + Step 4.5 清理后的 entry
        updates = {
            "shop/loaded.xlsx": {
                "mtime": 1700000000.0,
                "hash": "abc",
                "cold_start_marked": True,
                "marked_at": 1700000000.0,
            }
        }
        cleaned = _clean_processed_updates(updates)

        # 关键断言: cold_start_marked 字段必须保留 + 值为 False
        # (如果 del 字段, _file_changed ① 会判为老格式 → 死循环)
        assert "cold_start_marked" in cleaned["shop/loaded.xlsx"], (
            "加载成功后 cold_start_marked 字段必须保留, "
            "置 False 而非 del, 否则 _file_changed 会无限重载."
        )
        assert cleaned["shop/loaded.xlsx"]["cold_start_marked"] is False
        # last_processed_at 必须被添加
        assert "last_processed_at" in cleaned["shop/loaded.xlsx"]
        # mtime/hash 必须保留
        assert cleaned["shop/loaded.xlsx"]["mtime"] == 1700000000.0
        assert cleaned["shop/loaded.xlsx"]["hash"] == "abc"
        # marked_at 仍保留 (审计用, 没问题)
        assert "marked_at" in cleaned["shop/loaded.xlsx"]


class TestNormalProcessedFilesNotReloaded:
    """case 2: 正常 entry (cold_start_marked=False + mtime 匹配) 不重载."""

    def test_normal_processed_files_not_reloaded(self, tmp_path):
        """entry {mtime, hash, cold_start_marked=False, last_processed_at=...},
        文件 mtime 与 entry mtime 相同 → _file_changed 应返回 False.

        Sprint 24 技术债 #2: 直接调真函数 _file_changed (module-level).
        """
        from scripts.etl.ingest import _file_changed

        data_source = tmp_path / "data"
        data_source.mkdir()
        xlsx_path = data_source / "normal.xlsx"
        xlsx_path.write_bytes(b"normal content")

        # entry mtime 与文件 mtime 一致, cold_start 标志位 False,
        # last_processed_at 已记录 (Step 4.5 后的正常状态)
        current_mtime = xlsx_path.stat().st_mtime
        processed_files = {
            str(xlsx_path.relative_to(data_source)): {
                "mtime": current_mtime,
                "hash": "somehash",
                "cold_start_marked": False,
                "last_processed_at": time.time() - 3600,  # 1 小时前处理过
            }
        }

        # 字段语义断言 (前置条件检查)
        for key, rec in processed_files.items():
            assert "cold_start_marked" in rec, f"{key} 应有 cold_start_marked 字段"
            assert rec["cold_start_marked"] is False, (
                "正常处理完的 entry cold_start_marked 应为 False"
            )
            assert "last_processed_at" in rec, (
                "正常处理完的 entry 应记录 last_processed_at 时间戳"
            )
            assert rec["mtime"] == current_mtime, (
                "正常 entry mtime 应与文件 mtime 一致 (走短路返回 False)"
            )

        # 直接调真 _file_changed — mtime 短路返 False
        xlsx_stem_to_rel = {xlsx_path.stem: str(xlsx_path.relative_to(data_source))}
        result = _file_changed(xlsx_path, processed_files, data_source, xlsx_stem_to_rel)
        assert result is False, (
            "正常 entry (mtime 一致 + cold_start=False) 必须被 _file_changed "
            "判定为未变更, 走 ④ mtime 短路返 False. 实际: {result}"
        )


class TestMtimeChangedTriggersHashCheck:
    """case 3: mtime 变了但无 cold_start 标志, 必须走 hash 二次校验."""

    def test_mtime_changed_no_cold_start_flag_triggers_hash_check(self, tmp_path, monkeypatch):
        """entry {mtime: old, hash: 'abc', cold_start_marked=False},
        文件 mtime > old, hash 不同 → 必须返回 True (内容真变了).

        Sprint 24 技术债 #2: 直接调真函数 _file_changed (module-level).
        """
        from scripts.etl.ingest import _file_changed

        data_source = tmp_path / "data"
        data_source.mkdir()
        xlsx_path = data_source / "changed.xlsx"
        xlsx_path.write_bytes(b"new content")

        # entry 记录旧 mtime + 旧 hash, 无 cold_start 标志
        processed_files = {
            str(xlsx_path.relative_to(data_source)): {
                "mtime": xlsx_path.stat().st_mtime - 10,  # 比真实 mtime 旧 10s
                "hash": "old_hash_abc",
                "cold_start_marked": False,
                "last_processed_at": time.time() - 7200,
            }
        }

        # 前置条件断言
        for key, rec in processed_files.items():
            assert rec["cold_start_marked"] is False, "本 case 不应有冷启动标志"
            current_mtime = xlsx_path.stat().st_mtime
            old_mtime = rec["mtime"]
            assert current_mtime > old_mtime, "本 case 文件 mtime 应大于 entry mtime"
            assert rec["hash"] != "", "正常 entry 应有 hash 字段 (v2 格式要求)"

        # patch _get_file_hash 让它返新 hash (跟 entry 旧 hash 不同) → 走 ⑤ hash 比对
        monkeypatch.setattr(
            "scripts.etl.ingest._get_file_hash", lambda _f: "new_hash_xyz"
        )

        # 直接调真 _file_changed — 走 ④ mtime 短路失败 + ⑤ hash 不同 → 返 True
        xlsx_stem_to_rel = {xlsx_path.stem: str(xlsx_path.relative_to(data_source))}
        result = _file_changed(xlsx_path, processed_files, data_source, xlsx_stem_to_rel)
        assert result is True, (
            "mtime 变了 + hash 不同 必须触发 _file_changed 返 True "
            "(内容真变了, 走 ⑤ hash 比对路径). 实际: {result}"
        )


# ─────────────────────────────────────────────────────────────
# _clean_processed_updates 单测 (Step 4.5 清理逻辑)
# ─────────────────────────────────────────────────────────────

class TestColdStartMarkClearedAfterProcessing:
    """case 4: Step 4.5 成功后, _clean_processed_updates 必须移除 cold_start_marked."""

    def test_cold_start_mark_cleared_after_processing(self):
        """传入 {cold_start_marked: True, mtime, hash} 字典,
        断言输出 {cold_start_marked 字段不存在, last_processed_at 字段存在}.
        """
        from scripts.etl.ingest import _clean_processed_updates

        # 模拟冷启动登记的 updates (Step 4.5 还没清理)
        updates = {
            "shop/file1.xlsx": {
                "mtime": 1700000000.0,
                "hash": "abc123",
                "cold_start_marked": True,
                "marked_at": 1700000000.0,
            },
            "shop/file2.xlsx": {
                "mtime": 1700000001.0,
                "hash": "def456",
                "cold_start_marked": True,
                "marked_at": 1700000001.0,
            },
        }

        cleaned = _clean_processed_updates(updates)

        assert isinstance(cleaned, dict), "返类型应为 dict"
        assert set(cleaned.keys()) == {"shop/file1.xlsx", "shop/file2.xlsx"}, (
            "key 应保持不变"
        )

        for key, rec in cleaned.items():
            # ⚠️ 关键: 字段必须保留 (置 False), 不能 del.
            # 因为 _file_changed ① 判定条件是 'cold_start_marked' not in rec,
            # 如果 del 字段, 加载成功后 entry 命中 ① → 死循环全量重载.
            assert "cold_start_marked" in rec, (
                f"{key} 处理后必须保留 cold_start_marked 字段 (置 False), "
                f"不能 del (否则 _file_changed ① 会判为老格式, 每天全量重载)"
            )
            assert rec["cold_start_marked"] is False, (
                f"{key} 处理后 cold_start_marked 必须为 False "
                f"(表示已真正加载过, 下次走 mtime/hash 正常流程)"
            )
            assert "last_processed_at" in rec, (
                f"{key} 处理后必须追加 last_processed_at 时间戳"
            )
            assert isinstance(rec["last_processed_at"], (int, float)), (
                "last_processed_at 应为数值 (time.time())"
            )
            # mtime 和 hash 必须保留 (下次增量走正常 mtime/hash 短路)
            assert rec["mtime"] == updates[key]["mtime"]
            assert rec["hash"] == updates[key]["hash"]

    def test_clean_processed_updates_empty_input(self):
        """空 updates 不应抛错, 直接返空 dict."""
        from scripts.etl.ingest import _clean_processed_updates

        assert _clean_processed_updates({}) == {}
        assert _clean_processed_updates(None) is None


# ─────────────────────────────────────────────────────────────
# _mark_all_files_processed 端到端 (mock SHOP/MEMBER_DATA_SOURCE)
# ─────────────────────────────────────────────────────────────

class TestMarkAllFilesProcessedAddsColdStartFlag:
    """case 5: _mark_all_files_processed 写入的每个 entry 必须含 cold_start_marked=False.

    Sprint 24 P0-1 治根 (2026-06-16): 必须写 False, 不能再写 True.
    旧实现 True → _file_changed 路径 [B] 强制重读 → 197 个文件全重读 16-32h.
    新语义: False = "已登记", mtime 短路 (行 130) 兜住, 不触发 [B] 重读.
    真"需重读"由 [A] key not in processed_files 触发 (O2 增量新文件).
    """

    def test_mark_all_files_processed_adds_cold_start_flag(self, tmp_path, monkeypatch):
        """创建临时目录, 放 1 个 xlsx, mock SHOP/MEMBER_DATA_SOURCE 指向它,
        调用 _mark_all_files_processed, 读取生成的 tracker JSON,
        断言每个 entry 都有 cold_start_marked=False (已登记). Sprint 24+ P3 (v0.4.14.96)
        删了 marked_at 字段 (债 #5, ETL 内部无读取代码, 冗余), 所以不再断言该字段.
        """
        from scripts.etl import pipeline
        from scripts.etl import config as _config

        # Step 1: 准备临时数据源 (1 个 xlsx) + 空 Parquet 缓存目录
        # (空目录必须真创建, 否则 _mark_all_files_processed L794 会读生产 PARQUET_DATA_DIR,
        # 把 100+ parquet 当成 member 缓存, 污染测试断言)
        shop_dir = tmp_path / "shop"
        member_dir = tmp_path / "member"
        shop_dir.mkdir()
        member_dir.mkdir()
        pq_dir = tmp_path / "parquet_cache"
        (pq_dir / "shop").mkdir(parents=True)
        (pq_dir / "member").mkdir(parents=True)
        xlsx_path = shop_dir / "fake_data.xlsx"
        xlsx_path.write_bytes(b"fake xlsx content for cold start mark test")

        # Step 2: 准备临时 tracker 输出目录 (避免污染生产 /Users/.../data/processed)
        tracker_dir = tmp_path / "processed"
        tracker_dir.mkdir()
        shop_tracker = tracker_dir / "processed_files_shop.json"
        member_tracker = tracker_dir / "processed_files_member.json"

        def fake_processed_path(data_type):
            return tracker_dir / f"processed_files_{data_type}.json"

        # Step 3: 短路 _get_file_hash (避免读真文件 + xxhash 依赖)
        def fake_get_file_hash(file_path):
            return "fake_hash_for_test"

        # Step 4: monkeypatch 所有路径 + 哈希
        monkeypatch.setattr(pipeline, "SHOP_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(pipeline, "MEMBER_DATA_SOURCE", member_dir)
        monkeypatch.setattr(_config, "SHOP_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(_config, "MEMBER_DATA_SOURCE", member_dir)
        # 必须同时 patch PARQUET_DATA_DIR, 否则 _mark_all_files_processed L794
        # 会读生产 PARQUET_DATA_DIR 下的 100+ parquet 文件, 把所有缓存都标成
        # cold_start_marked=True 写入 tracker, 污染 member tracker 断言.
        monkeypatch.setattr(pipeline, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(_config, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(pipeline, "_get_processed_files_path", fake_processed_path)
        monkeypatch.setattr(_config, "_get_processed_files_path", fake_processed_path)
        monkeypatch.setattr(pipeline, "_get_file_hash", fake_get_file_hash)
        monkeypatch.setattr(_config, "_get_file_hash", fake_get_file_hash)

        # Step 5: 调用 _mark_all_files_processed
        pipeline._mark_all_files_processed()

        # Step 6: 读取生成的 tracker JSON
        assert shop_tracker.exists(), (
            f"_mark_all_files_processed 后应生成 {shop_tracker}"
        )
        with open(shop_tracker, "r", encoding="utf-8") as f:
            shop_processed = json.load(f)

        assert member_tracker.exists(), (
            f"_mark_all_files_processed 后应生成 {member_tracker}"
        )
        with open(member_tracker, "r", encoding="utf-8") as f:
            member_processed = json.load(f)

        # Step 7: 断言每个 entry 都有 cold_start_marked=False (已登记, 不触发 [B])
        assert "fake_data.xlsx" in shop_processed, (
            f"shop tracker 应含 fake_data.xlsx, 实际 keys: {list(shop_processed.keys())}"
        )
        shop_entry = shop_processed["fake_data.xlsx"]
        # Sprint 24 P0-1 治根: 必须写 False (而非 True), 否则 [B] rec.get('cold_start_marked')
        # 命中 True → 强制重读 197 个文件 → 16-32h 灾难
        assert shop_entry.get("cold_start_marked") is False, (
            f"shop entry 必须有 cold_start_marked=False (已登记, 不触发 [B] 重读), "
            f"实际: {shop_entry}. "
            f"⚠️ Sprint 24 P0-1 治根: True 会让 _file_changed 每次都重读所有文件"
        )
        # Sprint 24+ P3 (v0.4.14.96) 删 marked_at 字段 (债 #5, 冗余)
        assert "marked_at" not in shop_entry, (
            "shop entry 不应再含 marked_at 字段 (v0.4.14.96 债 #5 删)"
        )
        assert "mtime" in shop_entry
        assert shop_entry["hash"] == "fake_hash_for_test"

        # member 目录是空的, tracker 应该是空 dict (但文件已创建)
        assert member_processed == {}, (
            f"member 目录为空时, member tracker 应为空 dict, 实际: {member_processed}"
        )

    def test_mark_all_files_processed_then_file_changed_no_reload(self, tmp_path, monkeypatch):
        """Sprint 24 P0-1 治根回归测试: 写 tracker 后跑 _file_changed (mtime 一致)
        必须返 False (不重读), 证明冷启动登记不再触发 197 个文件全重读.

        旧实现 (cold_start_marked=True) 会被 [B] rec.get('cold_start_marked') 命中
        → _file_changed 返 True → 197 个文件全重读 16-32h.

        新实现 (cold_start_marked=False) 不会命中 [B], 走 mtime 短路
        (mtime <= old_mtime) → 返 False → 不重读.
        """
        from scripts.etl import pipeline
        from scripts.etl import config as _config

        # Step 1: 准备临时数据源 (1 个 xlsx)
        shop_dir = tmp_path / "shop"
        member_dir = tmp_path / "member"
        shop_dir.mkdir()
        member_dir.mkdir()
        xlsx_path = shop_dir / "data.xlsx"
        xlsx_path.write_bytes(b"data content for no-reload test")
        # 把 mtime 设到 1 小时前 (模拟"已登记"后文件未修改)
        import os
        one_hour_ago = time.time() - 3600
        os.utime(xlsx_path, (one_hour_ago, one_hour_ago))

        pq_dir = tmp_path / "parquet_cache"
        (pq_dir / "shop").mkdir(parents=True)
        (pq_dir / "member").mkdir(parents=True)

        tracker_dir = tmp_path / "processed"
        tracker_dir.mkdir()
        shop_tracker = tracker_dir / "processed_files_shop.json"

        def fake_processed_path(data_type):
            return tracker_dir / f"processed_files_{data_type}.json"

        def fake_get_file_hash(file_path):
            return "fake_hash_for_no_reload_test"

        # Step 2: monkeypatch
        monkeypatch.setattr(pipeline, "SHOP_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(pipeline, "MEMBER_DATA_SOURCE", member_dir)
        monkeypatch.setattr(_config, "SHOP_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(_config, "MEMBER_DATA_SOURCE", member_dir)
        monkeypatch.setattr(pipeline, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(_config, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(pipeline, "_get_processed_files_path", fake_processed_path)
        monkeypatch.setattr(_config, "_get_processed_files_path", fake_processed_path)
        monkeypatch.setattr(pipeline, "_get_file_hash", fake_get_file_hash)
        monkeypatch.setattr(_config, "_get_file_hash", fake_get_file_hash)

        # Step 3: 调 _mark_all_files_processed 写入 tracker
        pipeline._mark_all_files_processed()

        with open(shop_tracker) as f:
            shop_processed = json.load(f)

        # 把 xlsx mtime 恢复到 _time.time() 之后 (模拟"刚 _mark_all 写完后"时间流)
        # 实际场景: _mark_all_files_processed 跑在 ETL 前面, 写完 mtime=T1
        # ETL 增量跑时, 文件 mtime 还是 T1 (未修改) → mtime <= old_mtime
        # 我们让 xlsx 真实 mtime == entry mtime (都是 1 小时前), 模拟 mtime 一致
        new_mtime = one_hour_ago
        os.utime(xlsx_path, (new_mtime, new_mtime))
        # 但需要让 entry 写的是当前文件 mtime
        with open(shop_tracker) as f:
            shop_processed = json.load(f)
        # entry mtime 应是 1 小时前 (我们刚 utime 过)
        entry_mtime = shop_processed["data.xlsx"]["mtime"]
        assert entry_mtime == new_mtime, (
            f"测试前置: entry mtime ({entry_mtime}) 应等于文件 mtime ({new_mtime})"
        )

        # Step 4: 调真 _file_changed (Sprint 24 技术债 #2 抽到 module-level 后可独立单测)
        # 入口参数: (file_path, processed_files, data_source, xlsx_stem_to_rel)
        from scripts.etl.ingest import _file_changed

        rec = shop_processed["data.xlsx"]
        current_mtime = xlsx_path.stat().st_mtime

        # ③ 必须 False: cold_start_marked 写 False, [B] 不触发
        assert rec.get("cold_start_marked") is False, (
            f"⚠️ Sprint 24 P0-1 治根: entry cold_start_marked 必须 False, "
            f"实际 {rec.get('cold_start_marked')}, True 会让 [B] 强制重读"
        )
        # ② 必须 False: 字段存在, 不命中老格式判定
        assert "cold_start_marked" in rec, (
            "字段必须存在 (置 False), 删字段会命中 _file_changed ① 老格式判定"
        )
        # ④ mtime 一致 → False (不重读)
        assert current_mtime <= rec.get("mtime", 0), (
            f"测试前置: 文件 mtime ({current_mtime}) 应 <= entry mtime ({rec.get('mtime')})"
        )

        # 综合断言: 调真 _file_changed, 期望返 False
        xlsx_stem_to_rel = {xlsx_path.stem: str(xlsx_path.relative_to(shop_dir))}
        result = _file_changed(xlsx_path, shop_processed, shop_dir, xlsx_stem_to_rel)
        assert result is False, (
            f"⚠️ 冷启动登记后 _file_changed 必须返 False (mtime 一致), "
            f"实际 {result}. "
            f"如果 True, 意味着 197 个文件全部要重读 (16-32h 灾难)"
        )

    def test_mark_all_files_processed_idempotent_second_call(self, tmp_path, monkeypatch):
        """第二次调 _mark_all_files_processed 必须重新写入 cold_start_marked=False
        (即使上次 Step 4.5 清理过, 第二次全量跑批也要重新登记).

        Sprint 24 P0-1 治根: 必须写 False. 旧实现 True 触发 [B] 强制重读.
        """
        from scripts.etl import pipeline
        from scripts.etl import config as _config

        shop_dir = tmp_path / "shop"
        shop_dir.mkdir()
        (shop_dir / "f.xlsx").write_bytes(b"x")

        tracker_dir = tmp_path / "processed"
        tracker_dir.mkdir()

        # 空 Parquet 缓存目录, 防生产缓存污染
        pq_dir = tmp_path / "parquet_cache"
        (pq_dir / "shop").mkdir(parents=True)
        (pq_dir / "member").mkdir(parents=True)

        monkeypatch.setattr(pipeline, "SHOP_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(pipeline, "MEMBER_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(_config, "SHOP_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(_config, "MEMBER_DATA_SOURCE", shop_dir)
        monkeypatch.setattr(pipeline, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(_config, "PARQUET_DATA_DIR", pq_dir)
        monkeypatch.setattr(
            pipeline, "_get_processed_files_path",
            lambda dt: tracker_dir / f"processed_files_{dt}.json",
        )
        monkeypatch.setattr(
            _config, "_get_processed_files_path",
            lambda dt: tracker_dir / f"processed_files_{dt}.json",
        )
        monkeypatch.setattr(pipeline, "_get_file_hash", lambda _: "h")
        monkeypatch.setattr(_config, "_get_file_hash", lambda _: "h")

        # 第一次: 写入 cold_start_marked=False (Sprint 24 P0-1 治根)
        pipeline._mark_all_files_processed()
        shop_tracker = tracker_dir / "processed_files_shop.json"
        with open(shop_tracker) as f:
            first = json.load(f)
        assert first["f.xlsx"]["cold_start_marked"] is False

        # 第二次: 必须重新写 cold_start_marked=False (即使 tracker 已存在)
        pipeline._mark_all_files_processed()
        with open(shop_tracker) as f:
            second = json.load(f)
        assert second["f.xlsx"]["cold_start_marked"] is False, (
            "第二次 _mark_all_files_processed 必须把 cold_start_marked 置 False "
            "(Sprint 24 P0-1: 已登记语义, 不触发 [B] 强制重读)."
        )
