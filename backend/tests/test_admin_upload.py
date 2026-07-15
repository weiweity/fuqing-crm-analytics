"""Sprint 205+ Admin Upload Sprint 1: 全量回归 case.

跟 v5 prompt §8.1 + Codex Stage 3 B1-B6/L1-L3 1:1 stable 永久规则化沿用,
跟 L4.50 + L4.60 + L4.34 1:1 stable 永久规则链配套.
所有文件系统测试用 tmp_path (跟 v5 prompt "禁测试写入生产" 1:1 stable).

职责描述 (不写固定 case 数量, 避免后续漂移):
- 第 1 部分: upload/config/security (admin auth gate, 10 数据源, 文件名校验,
             path traversal, 大小限制, 业务内容校验, sprint 1 不动正式 target)
- 第 2 部分: registry/concurrency/idempotency (registry 写入/恢复, 幂等命中清理,
             dedup 重复 409, 跨 thread 并发不丢记录)
- 第 3 部分: C-1 campaign-schedule fail-fast (3 case: 文件缺失/读取失败/缺列)
- 第 4 部分: P1/P2 + Stage 3 B/L 回归 (B1 fsync 失败 cleanup / B2 post-replace
             保留 / B3 SPU mapping preflight / B5 channel-rules staged path /
             B6 registry 严格结构校验 / L1 Idempotency-Key 限制 / L3 多 reader
             并发恢复等)
"""
from __future__ import annotations

import json
import threading
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import admin_upload as svc


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tmp_paths(tmp_path):
    """注入 staging / registry / lock / backup 路径到 admin_upload service."""
    staging = tmp_path / "staging"
    registry = tmp_path / "upload_registry.json"
    lock = tmp_path / "upload_registry.lock"
    backup = tmp_path / "upload_registry.json.bak"
    return {"staging": staging, "registry": registry, "lock": lock, "backup": backup}


@pytest.fixture
def admin_token(client):
    payload = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"}).json()
    return payload["token"]


@pytest.fixture
def fqsw_token(client):
    payload = client.post("/api/v1/auth/login", json={"username": "fqsw", "password": "fqsw888"}).json()
    return payload["token"]


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def fqsw_headers(fqsw_token):
    return {"Authorization": f"Bearer {fqsw_token}"}


@pytest.fixture
def patch_paths(tmp_paths, monkeypatch):
    """monkeypatch 服务层 default 路径 → tmp_path (避免污染真实生产路径)."""
    monkeypatch.setattr(svc, "_DEFAULT_STAGING_ROOT", tmp_paths["staging"])
    monkeypatch.setattr(svc, "_DEFAULT_REGISTRY_PATH", tmp_paths["registry"])
    monkeypatch.setattr(svc, "_DEFAULT_REGISTRY_LOCK", tmp_paths["lock"])
    monkeypatch.setattr(svc, "_DEFAULT_REGISTRY_BACKUP", tmp_paths["backup"])
    return tmp_paths


# ─────────────────────────────────────────────────────────────
# 第 1 部分: upload/config/security 11 case
# ─────────────────────────────────────────────────────────────
def test_upload_config_returns_exactly_10_sources(client, admin_headers):
    resp = client.get("/api/v1/admin/upload-config", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["sources"]) == 10
    types = {s["business_type"] for s in data["sources"]}
    assert types == {
        "shop", "member", "status-refresh", "taoke", "live", "visitor",
        "spu-mapping", "taoke-product", "channel-rules", "campaign-schedule",
    }
    assert data["max_upload_bytes"] == 100 * 1024 * 1024


def test_upload_config_does_not_expose_absolute_paths(client, admin_headers):
    resp = client.get("/api/v1/admin/upload-config", headers=admin_headers)
    text = resp.text
    # 禁出现的字符串
    assert "/Users/" not in text
    assert "staged_path" not in text
    assert "target_path" not in text
    assert "staging_path" not in text


def test_unauthenticated_returns_401(client):
    resp = client.get("/api/v1/admin/upload-config")
    assert resp.status_code == 401
    # 未登录走 auth_middleware 拦截, detail 是字符串 ("未提供认证令牌");
    # 已登录但非 admin 走 require_admin → JSON object with code=ADMIN_REQUIRED.
    assert "detail" in resp.json()


def test_non_admin_returns_403(client, fqsw_headers):
    resp = client.get("/api/v1/admin/upload-config", headers=fqsw_headers)
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "ADMIN_REQUIRED"


def test_unknown_business_type_returns_400(client, admin_headers, patch_paths):
    files = {"file": ("shop.csv", b"order_id\n1\n", "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "nonexistent"},
        files=files,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "UNKNOWN_BUSINESS_TYPE"


def test_invalid_extension_returns_422(client, admin_headers, patch_paths):
    # shop 限定 .xlsx, 上传 .csv 应 422
    files = {"file": ("shop.csv", b"order_id\n1\n", "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "shop"},
        files=files,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "INVALID_EXTENSION"


def test_path_traversal_filename_returns_400(client, admin_headers, patch_paths):
    # 文件名含 ..
    files = {"file": ("../../etc/passwd.csv", b"x\n", "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "INVALID_FILENAME"


def test_empty_file_returns_400(client, admin_headers, patch_paths):
    files = {"file": ("taoke.csv", b"", "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "EMPTY_FILE"


def test_oversized_stream_returns_413_and_removes_part(client, admin_headers, patch_paths):
    """构造 > 100MB 内容, 验证 413 + staging 0 残留 (part/final/空 UUID 目录).

    P2-2 修法: 严格断言 413, 不再接受 400 fallback. 同时验证 staging 完全干净
    (0 payload.part, 0 payload.{ext}, 0 空 UUID 子目录).
    """
    # 101 MB 重复 header (taoke 合法列头)
    header = "淘宝父订单编号\n".encode("utf-8")
    payload = header + b"a" * (101 * 1024 * 1024)
    files = {"file": ("taoke.csv", payload, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    # 严格断言 413 (admin_upload 服务层抛 FileTooLarge)
    assert resp.status_code == 413, f"期望 413, 实得 {resp.status_code} {resp.text}"
    assert resp.json()["detail"]["code"] == "PAYLOAD_TOO_LARGE"

    # staging 完全干净: 0 part, 0 final, 0 空 UUID 目录
    parts = list(patch_paths["staging"].rglob("payload.part"))
    finals = list(patch_paths["staging"].rglob("payload.*"))
    all_subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert parts == [], f"应有 0 个 part 残留, 实得 {parts}"
    assert finals == [], f"应有 0 个 payload 残留, 实得 {finals}"
    assert all_subdirs == [], f"应有 0 个空 UUID 目录, 实得 {all_subdirs}"


def test_wrong_business_content_returns_422(client, admin_headers, patch_paths):
    # taoke 必需列 "淘宝父订单编号", 上传只含 other_col 的 CSV
    csv_bytes = "other_col\nfoo\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 422
    assert resp.json()["detail"]["code"] == "VALIDATION_FAILED"


def test_sprint1_upload_never_changes_active_target(client, admin_headers, patch_paths, monkeypatch):
    """Sprint 1 只写 staging, 上传 taoke 时 monkeypatch TAOKE_DATA_SOURCE 验证不变.

    P1-5 修法: 之前测上传 taoke 却只检查 shop/member 路径, 缺针对性.
    现在 monkeypatch 实际被写入的 business_type (taoke) 的 target, 验证正式路径 0 字节变化.

    Codex Stage 4 二审加固: 加显式 monkeypatch 生效断言 (B4 修法), 防止 B4 假绿 —
    之前测试因为 upload 不写 target_path, 即使 monkeypatch 没生效也会过.
    现在显式验证:
    1. monkeypatch 后 svc.get_source() 立即反映新值 (无 module-level cache)
    2. 二次 monkeypatch 也能立即生效
    3. 上传后 active target 字节级不变
    """
    from backend import config as cfg
    from backend.services import admin_upload as _svc

    # mock taoke 正式路径 → tmp_path 副本, 验证写入仅发生在 staging 不在副本
    fake_taoke = patch_paths["staging"].parent / "taoke_dir"
    fake_taoke.mkdir()
    taoke_marker = fake_taoke / "original.csv"
    taoke_marker.write_text("original_taoke_content", encoding="utf-8")
    original_taoke_bytes = taoke_marker.read_bytes()

    # 第一步: monkeypatch 后立即验证 svc.get_source() 反映新值 (B4 防假绿)
    monkeypatch.setattr(cfg, "TAOKE_DATA_SOURCE", fake_taoke)
    src_after_patch_a = _svc.get_source("taoke")
    assert src_after_patch_a is not None, "taoke source 必须存在"
    assert src_after_patch_a.target_path.resolve() == fake_taoke.resolve(), (
        f"monkeypatch 后 svc.get_source('taoke').target_path 应等于 fake_taoke, "
        f"实得 {src_after_patch_a.target_path}"
    )

    # 第二步: 二次 monkeypatch 验证 config 是动态读 (B4 移除 _SOURCES cache 1:1 stable)
    fake_taoke_b = patch_paths["staging"].parent / "taoke_dir_b"
    fake_taoke_b.mkdir()
    monkeypatch.setattr(cfg, "TAOKE_DATA_SOURCE", fake_taoke_b)
    src_after_patch_b = _svc.get_source("taoke")
    assert src_after_patch_b.target_path.resolve() == fake_taoke_b.resolve(), (
        f"二次 monkeypatch 后 svc.get_source('taoke').target_path 应等于 fake_taoke_b, "
        f"实得 {src_after_patch_b.target_path}"
    )

    # 恢复成 fake_taoke 跑后续断言
    monkeypatch.setattr(cfg, "TAOKE_DATA_SOURCE", fake_taoke)

    # 第三步: 上传 taoke, 验证正式路径 0 字节变化
    csv_bytes = "淘宝父订单编号\n123\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201

    # 验证 fake_taoke 字节级不变 + 0 payload 文件
    assert taoke_marker.read_bytes() == original_taoke_bytes
    assert list(fake_taoke.glob("payload*")) == []

    # 第四步: registry staged_path 不应含 fake_taoke 绝对路径
    reg_data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_data["uploads"]) == 1
    assert fake_taoke.resolve().as_posix() not in reg_data["uploads"][0]["staged_path"]


# ─────────────────────────────────────────────────────────────
# 第 2 部分: registry/concurrency/idempotency 7 case
# ─────────────────────────────────────────────────────────────
def test_successful_upload_writes_staged_registry_record(client, admin_headers, patch_paths):
    csv_bytes = "淘宝父订单编号\n123\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["duplicate"] is False
    assert body["upload"]["business_type"] == "taoke"
    assert body["upload"]["size_bytes"] == len(csv_bytes)
    assert len(body["upload"]["sha256"]) == 64
    # registry 文件已写
    assert patch_paths["registry"].exists()
    data = json.loads(patch_paths["registry"].read_text())
    assert len(data["uploads"]) == 1
    assert data["uploads"][0]["business_type"] == "taoke"


def test_duplicate_business_type_and_hash_returns_409(client, admin_headers, patch_paths):
    csv_bytes = "淘宝父订单编号\n123\n".encode("utf-8")
    files1 = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp1 = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files1,
    )
    assert resp1.status_code == 201
    # 第二次相同 business_type + 相同 sha256
    files2 = {"file": ("taoke_v2.csv", csv_bytes, "text/csv")}
    resp2 = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files2,
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "DUPLICATE_UPLOAD"


def test_same_idempotency_key_same_payload_returns_existing_record(client, admin_headers, patch_paths):
    csv_bytes = "淘宝父订单编号\n123\n".encode("utf-8")
    headers = {**admin_headers, "Idempotency-Key": "idem-001"}
    files1 = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp1 = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files1,
    )
    assert resp1.status_code == 201
    first_body = resp1.json()
    # 相同 key + 相同内容 → 200 命中
    files2 = {"file": ("taoke_again.csv", csv_bytes, "text/csv")}
    resp2 = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files2,
    )
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True
    assert resp2.json()["upload"]["upload_id"] == first_body["upload"]["upload_id"]


def test_same_idempotency_key_different_payload_returns_409(client, admin_headers, patch_paths):
    headers = {**admin_headers, "Idempotency-Key": "idem-conflict"}
    files1 = {"file": ("taoke1.csv", "淘宝父订单编号\n123\n".encode("utf-8"), "text/csv")}
    resp1 = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files1,
    )
    assert resp1.status_code == 201
    # 相同 key + 不同 sha256 → 409
    files2 = {"file": ("taoke2.csv", "淘宝父订单编号\n456\n".encode("utf-8"), "text/csv")}
    resp2 = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files2,
    )
    assert resp2.status_code == 409
    assert resp2.json()["detail"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_registry_atomic_write_leaves_valid_json(client, admin_headers, patch_paths):
    """多次上传后, registry 文件 JSON 始终可解析."""
    for i in range(5):
        csv_bytes = f"淘宝父订单编号\n{i}\n".encode("utf-8")
        files = {"file": (f"taoke_{i}.csv", csv_bytes, "text/csv")}
        resp = client.post(
            "/api/v1/admin/upload",
            headers=admin_headers,
            data={"business_type": "taoke"},
            files=files,
        )
        assert resp.status_code == 201
        # 中途验证 JSON 完整
        data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
        assert isinstance(data.get("uploads"), list)
        assert len(data["uploads"]) == i + 1


def test_corrupt_registry_recovers_from_backup(client, admin_headers, patch_paths):
    """先正常上传, 然后人工损坏主 registry, 验证 GET /uploads 能从 .bak 恢复."""
    csv_bytes = "淘宝父订单编号\n1\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201
    # 第二次上传触发 .bak 备份
    csv_bytes2 = "淘宝父订单编号\n2\n".encode("utf-8")
    files2 = {"file": ("taoke2.csv", csv_bytes2, "text/csv")}
    client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files2,
    )
    # 损坏主 registry
    patch_paths["registry"].write_text("this is not json {{{")
    # GET /uploads 应恢复 (从 .bak), 返 200 + items
    resp = client.get("/api/v1/admin/uploads", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    # 恢复后至少有 1 条 (上次成功的主内容备份到 .bak)
    assert data["total"] >= 1

    # Codex 补强: GET 后主 registry 必须重新成为合法 JSON (P2-1 LOCK_EX 恢复后写回)
    main_text = patch_paths["registry"].read_text(encoding="utf-8")
    json.loads(main_text)  # 合法 JSON 解析不抛
    # 恢复内容跟 .bak 一致 (因为主 corrupt 时 .bak 是上一份有效内容)
    bak_text = patch_paths["backup"].read_text(encoding="utf-8")
    # 主恢复后内容应该跟原 backup 一致 (原子写 .bak → .bak → 主; 第二次写时 .bak 是第一次的主)
    main_data = json.loads(main_text)
    bak_data = json.loads(bak_text)
    assert main_data.get("uploads") == bak_data.get("uploads"), (
        f"主 registry 恢复后内容应跟 .bak 一致. main={main_data} bak={bak_data}"
    )


def test_concurrent_registry_updates_do_not_lose_records(client, admin_headers, patch_paths):
    """多线程并发上传不同 sha256, 不丢记录."""
    results = []
    errors = []

    def worker(i: int):
        try:
            # 每个 thread 不同内容 → 不同 sha256
            csv_bytes = f"淘宝父订单编号\n{i}\n".encode("utf-8")
            files = {"file": (f"taoke_{i}.csv", csv_bytes, "text/csv")}
            resp = client.post(
                "/api/v1/admin/upload",
                headers=admin_headers,
                data={"business_type": "taoke"},
                files=files,
            )
            results.append(resp.status_code)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    # 不允许有错误
    assert not errors, f"并发上传错误: {errors}"
    # 全部 201 (不同 sha256)
    assert all(s == 201 for s in results), f"并发上传状态码: {results}"
    # registry 完整性: 5 条全在
    data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(data["uploads"]) == 5


# ─────────────────────────────────────────────────────────────
# 第 3 部分: C-1 campaign-schedule fail-fast 3 case
# ─────────────────────────────────────────────────────────────
def test_campaign_schedule_missing_file_raises(tmp_path, monkeypatch):
    """CAMPAIGN_SCHEDULE_SOURCE 不存在 → FileNotFoundError."""
    from scripts.etl.pipeline import _refresh_campaign_schedule_impl

    fake = tmp_path / "no_such_file.csv"
    # pipeline.py 函数内 from backend.config import CAMPAIGN_SCHEDULE_SOURCE
    # 每次调用都重新读, monkeypatch backend.config 的 module attribute 即生效
    monkeypatch.setattr("backend.config.CAMPAIGN_SCHEDULE_SOURCE", fake)
    with pytest.raises(FileNotFoundError, match="campaign_schedule 数据源不存在"):
        _refresh_campaign_schedule_impl()


def test_campaign_schedule_read_error_raises(tmp_path, monkeypatch):
    """CAMPAIGN_SCHEDULE_SOURCE 内容非法 → RuntimeError with __cause__.

    Codex 补强: 严格断言 RuntimeError.__cause__ is not None (raise ... from exc 1:1 stable).
    """
    from scripts.etl.pipeline import _refresh_campaign_schedule_impl

    # 用不可解析的二进制内容触发 pandas 抛异常
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\x00\x00\x00 not csv at all \x99\x99")
    monkeypatch.setattr("backend.config.CAMPAIGN_SCHEDULE_SOURCE", bad)
    with pytest.raises(RuntimeError, match="campaign_schedule CSV 读取失败") as exc_info:
        _refresh_campaign_schedule_impl()
    # 严格断言 __cause__ 非空 (raise ... from exc)
    assert exc_info.value.__cause__ is not None, (
        f"RuntimeError 必须用 raise ... from exc 携带原始异常, 实得 __cause__ = {exc_info.value.__cause__}"
    )


def test_campaign_schedule_missing_columns_raises(tmp_path, monkeypatch):
    """CSV 缺必需列 → ValueError, 消息列出具体 missing 列名.

    Codex 补强: 断言异常消息包含每个具体缺失列 (year/活动名称/开始时间/结束时间).
    """
    from scripts.etl.pipeline import _refresh_campaign_schedule_impl

    # 只含 1 列, 缺所有必需列
    csv_path = tmp_path / "no_cols.csv"
    csv_path.write_text("only_one_col\nfoo\n", encoding="utf-8")
    monkeypatch.setattr("backend.config.CAMPAIGN_SCHEDULE_SOURCE", csv_path)
    with pytest.raises(ValueError, match="campaign_schedule 缺少必需列") as exc_info:
        _refresh_campaign_schedule_impl()
    msg = str(exc_info.value)
    # 消息必须列出 4 个缺失列中的至少 3 个 (跟 v5 prompt 1:1 stable)
    for col in ("year", "活动名称", "开始时间", "结束时间"):
        assert col in msg, f"ValueError 消息必须列出缺失列 '{col}', 实得: {msg}"

# ─────────────────────────────────────────────────────────────
# 第 4 部分: P1/P2 修复回归 case (v5 prompt 修订轮)
# ─────────────────────────────────────────────────────────────
# P1-2: 幂等命中清理 staging
def test_idempotency_hit_cleans_up_duplicate_payload(client, admin_headers, patch_paths):
    """P1-2 修法: 同一 Idempotency-Key + 同一 payload 连续两次, 第二次 200 命中, 但 staging 只 1 个 payload + 0 空目录."""
    csv_bytes = "淘宝父订单编号\n123\n".encode("utf-8")
    headers = {**admin_headers, "Idempotency-Key": "idem-p1-2"}

    files1 = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp1 = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files1,
    )
    assert resp1.status_code == 201
    first_upload_id = resp1.json()["upload"]["upload_id"]

    # 第二次 (相同 key + 相同 payload) → 200 idempotent hit
    files2 = {"file": ("taoke_again.csv", csv_bytes, "text/csv")}
    resp2 = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files2,
    )
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True
    assert resp2.json()["upload"]["upload_id"] == first_upload_id

    # 验证: registry 只有 1 条
    reg_data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_data["uploads"]) == 1, f"幂等命中后应有 1 条 registry 记录, 实得 {len(reg_data['uploads'])}"

    # 验证: staging 只有 1 个 payload 文件 (第一次写的)
    all_payloads = list(patch_paths["staging"].rglob("payload.*"))
    assert len(all_payloads) == 1, f"幂等命中后应有 1 个 payload, 实得 {all_payloads}"

    # 验证: 0 个空 UUID 目录 (第二次的 UUID 子目录被清理)
    all_subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert len(all_subdirs) == 1, (
        f"幂等命中后应有 1 个非空 UUID 目录 (含 payload), 实得 {all_subdirs}"
    )
    # 唯一子目录应等于 first_upload_id
    assert all_subdirs[0].name == first_upload_id
    # 唯一子目录非空 (含 payload)
    assert any(all_subdirs[0].iterdir()), f"UUID 目录 {all_subdirs[0]} 应非空"


# P1-1: channel-rules 校验真实读 staged (fail-closed)
def test_channel_rules_validation_reads_staged_path(client, admin_headers, patch_paths, monkeypatch):
    """P1-1 修法: 上传 channel-rules 时, 校验真实读取本次 staged 文件, 不读正式数据源.

    1. 正式 channel-rules 有效
    2. 上传 staged 文件列完全错误 → 422 VALIDATION_FAILED
    3. 不允许退化宽松
    """
    from backend import config as cfg

    # 正式 channel-rules 占位 + 标记
    fake_channel_rules = patch_paths["staging"].parent / "channel_rules_official.csv"
    fake_channel_rules.write_text(
        "关键词,渠道\n抖音,抖音渠道\n", encoding="utf-8"
    )
    monkeypatch.setattr(cfg, "CHANNEL_RULES_SOURCE", fake_channel_rules)

    # 上传时 staged 列完全错
    bad_staged = "only_one_col\n".encode("utf-8")
    files = {"file": ("channel.csv", bad_staged, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "channel-rules"},
        files=files,
    )
    # 422 (只有表头无数据行, P2-2 fail-closed)
    assert resp.status_code == 422, f"channel-rules 表头only 应 422, 实得 {resp.status_code} {resp.text}"
    assert resp.json()["detail"]["code"] == "VALIDATION_FAILED"

    # 正式 channel-rules 字节级不变 (没被改写)
    assert fake_channel_rules.read_text(encoding="utf-8") == "关键词,渠道\n抖音,抖音渠道\n"


def test_channel_rules_validation_accepts_legal_staged(client, admin_headers, patch_paths, monkeypatch):
    """P1-1 修法补强: 合法 staged channel-rules (2 列 keyword+channel) → 201."""
    from backend import config as cfg

    fake_channel_rules = patch_paths["staging"].parent / "channel_rules_official.csv"
    fake_channel_rules.write_text("关键词,渠道\nfake,虚假渠道\n", encoding="utf-8")
    monkeypatch.setattr(cfg, "CHANNEL_RULES_SOURCE", fake_channel_rules)

    # 上传合法 2 列 channel-rules (staged 应独立于正式)
    good_staged = "关键词,渠道\n抖音,抖音渠道\n小红书,小红书渠道\n".encode("utf-8")
    files = {"file": ("channel.csv", good_staged, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "channel-rules"},
        files=files,
    )
    assert resp.status_code == 201, f"合法 staged 应 201, 实得 {resp.status_code} {resp.text}"


# P1-3: post_upload 改同步 def 后行为不变 (201/200/409/422)
def test_post_upload_remains_sync_def_no_event_loop_block(client, admin_headers, patch_paths):
    """P1-3 修法: post_upload 是 def 不是 async def. 行为 (201/200/409/422) 不变."""
    import inspect
    from backend.routers.admin import post_upload
    # 签名应该是 def 不是 async def
    assert not inspect.iscoroutinefunction(post_upload), (
        "post_upload 必须是普通 def (FastAPI threadpool), 不能是 async def"
    )

    # 行为不变: 正常 taoke 上传 → 201
    csv_bytes = "淘宝父订单编号\n100\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201

    # 重复 → 409
    resp2 = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files={"file": ("taoke_dup.csv", csv_bytes, "text/csv")},
    )
    assert resp2.status_code == 409

    # 业务校验失败 → 422
    bad_csv = "wrong_col\nfoo\n".encode("utf-8")
    resp3 = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files={"file": ("taoke_bad.csv", bad_csv, "text/csv")},
    )
    assert resp3.status_code == 422


# P1-4: OpenAPI 契约补全
def test_openapi_post_upload_contract(client):
    """P1-4 修法: OpenAPI /api/v1/admin/upload 响应声明 200/201/400/401/403/409/413/422/500.

    Codex Stage 4 三审加固: 200/201 必须精确指向 #/components/schemas/UploadResponse,
    不能用"检查 schema 是否包含任意 ref 键"这种弱断言 (任何 ref 键都通过, 即使
    指向错误 schema). L3 测试 test_l3_openapi_admin_schemas_have_correct_refs
    负责跨 endpoint 精确 schema 映射, 本测试专注 upload endpoint 整体响应声明
    + ref 精度.
    """
    spec = client.get("/openapi.json").json()
    upload_spec = spec["paths"]["/api/v1/admin/upload"]["post"]
    responses = upload_spec["responses"]
    # 必含状态码
    for code in ("200", "201", "400", "401", "403", "409", "413", "422", "500"):
        assert code in responses, f"OpenAPI /upload 必声明 {code}, 实际 {list(responses.keys())}"
    # 201 默认 schema 精确指向 UploadResponse
    upload_response_ref = "#/components/schemas/UploadResponse"
    schema_201 = responses["201"]["content"]["application/json"]["schema"]
    assert schema_201.get("$ref") == upload_response_ref, (
        f"201 响应 schema 必须指向 UploadResponse, 实得 {schema_201.get('$ref')!r}"
    )
    # 200 schema 也精确指向 UploadResponse (idempotent hit)
    schema_200 = responses["200"]["content"]["application/json"]["schema"]
    assert schema_200.get("$ref") == upload_response_ref, (
        f"200 响应 schema 必须指向 UploadResponse, 实得 {schema_200.get('$ref')!r}"
    )


# P2-2: CSV 只有表头无数据行 → 422
def test_csv_header_only_returns_422(client, admin_headers, patch_paths):
    """P2-2 修法: CSV 只有表头 (1 行, N 列) → ValidationFailed 422."""
    csv_bytes = "淘宝父订单编号\n".encode("utf-8")  # 只有表头, 无数据行
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 422, f"CSV 只有表头应 422, 实得 {resp.status_code}"
    assert "表头" in resp.json()["detail"]["message"] or "无数据" in resp.json()["detail"]["message"]


# P2-3: GBK 编码 taoke 文件合法
def test_taoke_gbk_encoding_passes(client, admin_headers, patch_paths):
    """P2-3 修法: 业务列校验复用 _try_csv 已检测成功编码, GBK taoke 文件可过."""
    # 构造 GBK 编码的合法 taoke 文件 (中文列名 UTF-8, 内容 GBK 都可, 只要列名识别对)
    gbk_csv = "淘宝父订单编号\n123456\n".encode("gbk")
    files = {"file": ("taoke.csv", gbk_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201, (
        f"GBK 编码 taoke 应 201, 实得 {resp.status_code} {resp.text}"
    )


# P2-4: username 不 strip, "admin" 命中, " admin " 不命中
def test_is_admin_username_exact_match_no_strip(monkeypatch):
    """P2-4 修法: 配置项 strip, username 走原始字符串精确匹配."""
    from backend.routers.auth import is_admin_username
    monkeypatch.setenv("FQ_CRM_ADMINS", "admin")
    # "admin" 命中
    assert is_admin_username("admin") is True
    # " admin " (带空格) 不命中 (username 不 strip)
    assert is_admin_username(" admin ") is False
    # "Admin" (大小写不同) 不命中 (大小写敏感)
    assert is_admin_username("Admin") is False
    # None / 空 / 纯空白 → False
    assert is_admin_username(None) is False
    assert is_admin_username("") is False
    assert is_admin_username("   ") is False

    # 配置项多 admin 时仍精确匹配
    monkeypatch.setenv("FQ_CRM_ADMINS", "admin,fqsw")
    assert is_admin_username("admin") is True
    assert is_admin_username("fqsw") is True
    assert is_admin_username(" admin ") is False  # 配置项的 fqsw 也精确匹配


# P2-6: ZIP Windows 路径被拒绝
def test_zip_windows_absolute_path_rejected(tmp_path):
    """P2-6 修法: Windows 绝对路径 (C:\\evil.csv) / UNC (\\\\server\\share\\x) / 反斜杠路径 都被拒."""
    from backend.services.admin_upload import _try_zip

    # 构造含 Windows drive letter 的 ZIP
    bad_zip_path = tmp_path / "win_bad.zip"
    with zipfile.ZipFile(bad_zip_path, "w") as zf:
        zf.writestr("C:/evil.csv", "id\n1\n")

    from backend.services.admin_upload import ValidationFailed
    with pytest.raises(ValidationFailed, match="Windows drive"):
        _try_zip(bad_zip_path)

    # UNC path
    unc_zip = tmp_path / "unc.zip"
    with zipfile.ZipFile(unc_zip, "w") as zf:
        zf.writestr("\\\\server\\share\\x.csv", "id\n1\n")
    with pytest.raises(ValidationFailed, match="路径非法|UNC|反斜杠"):
        _try_zip(unc_zip)

    # 反斜杠路径 (单 backslash member)
    backslash_zip = tmp_path / "bs.zip"
    with zipfile.ZipFile(backslash_zip, "w") as zf:
        zf.writestr("sub\\evil.csv", "id\n1\n")
    with pytest.raises(ValidationFailed, match="反斜杠"):
        _try_zip(backslash_zip)


# P2-1: 多进程并发写 registry 不丢记录 (multiprocessing 真实跨进程)
def test_multiprocess_registry_updates_do_not_lose_records(patch_paths):
    """P2-1 修法: multiprocessing 真实跨进程并发 5 worker, 验证不丢记录.

    用 multiprocessing 而非 threading 走 OS 级 flock, 跟 fcntl.flock
    跨进程行为对齐.
    """
    import multiprocessing

    registry_path = patch_paths["registry"]
    lock_path = patch_paths["lock"]

    # 初始化 registry 为空
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps({"uploads": []}))

    def worker(idx: int, reg_path_str: str, lock_path_str: str) -> int:
        """子进程: 走 svc.upload 入口 (跟 admin router 行为一致)."""
        from pathlib import Path as _P

        # 子进程 import admin_upload, 每个 worker 独立 module 拷贝
        from backend.services import admin_upload as _svc

        import io

        reg_p = _P(reg_path_str)
        lock_p = _P(lock_path_str)
        # 每个 worker 不同 sha256 (避免 dedup 命中)
        csv_bytes = f"淘宝父订单编号\n{idx * 1000}\n".encode("utf-8")
        try:
            _svc.upload(
                business_type="taoke",
                file_obj=io.BytesIO(csv_bytes),
                original_filename=f"taoke_mp_{idx}.csv",
                uploaded_by="admin",
                staging_root=_P(reg_p.parent.parent / "data" / "processed" / "admin_uploads" / "staging"),
                registry_path=reg_p,
                lock_path=lock_p,
                backup_path=_P(str(reg_p) + ".bak"),
            )
            return idx
        except Exception:  # noqa: BLE001
            return -1 * (idx + 100)

    # 5 子进程并发
    ctx = multiprocessing.get_context("fork")  # macOS Python 3.14
    procs = []
    for i in range(5):
        p = ctx.Process(
            target=worker,
            args=(i, str(registry_path), str(lock_path)),
        )
        p.start()
        procs.append(p)
    for p in procs:
        p.join(timeout=30)

    # 验证 5 worker 全部成功
    reg_data = json.loads(registry_path.read_text(encoding="utf-8"))
    assert len(reg_data["uploads"]) == 5, (
        f"5 个 multiprocessing worker 应写 5 条, 实得 {len(reg_data['uploads'])}"
    )

    # 验证每个 upload 的 sha256 唯一 (跟 idx 一一对应)
    sha_set = {u["sha256"] for u in reg_data["uploads"]}
    assert len(sha_set) == 5, f"5 个 upload sha256 必须全不同, 实得 {sha_set}"


# ─────────────────────────────────────────────────────────────
# 第 5 部分: Stage 3 复核 B1-B6 + L1-L3 回归 case
# ─────────────────────────────────────────────────────────────

# B1: rename 成功后 fsync 目录失败 → 整个 staging UUID 子目录必须清理
def test_b1_fsync_directory_failure_cleans_up_staging_subdir(client, admin_headers, patch_paths, monkeypatch):
    """B1: 模拟 _fsync_directory 抛 OSError, 验证 staging/{upload_id}/ 完全清理.

    直接调 svc.upload 走代码路径 (TestClient 内部 anyio ExceptionGroup 包装
    让 status 不可靠, 但 cleanup 行为直接调 svc.upload 可测).
    """
    from backend.services import admin_upload as _svc
    import io

    def _fake_fsync_directory(path):
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(_svc, "_fsync_directory", _fake_fsync_directory)

    # 直接走 svc.upload (跟 router post_upload 调用一致, 但不走 anyio 包装)
    csv_bytes = "淘宝父订单编号\n123\n".encode("utf-8")
    raised = None
    try:
        _svc.upload(
            business_type="taoke",
            file_obj=io.BytesIO(csv_bytes),
            original_filename="taoke.csv",
            uploaded_by="admin",
        )
    except _svc.AdminUploadError as exc:
        raised = exc
    except OSError:
        # B1 直接抛 OSError 也接受 — except 仍跑 cleanup
        raised = "OSError"

    # 必须抛错 (cleanup 后 re-raise)
    assert raised is not None, "B1: fsync 失败应抛错 (cleanup 后 re-raise)"

    # 验证 staging 完全干净: 0 payload.part + 0 payload.{ext} + 0 UUID 子目录
    parts = list(patch_paths["staging"].rglob("payload.part"))
    finals = list(patch_paths["staging"].rglob("payload.*"))
    subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert parts == [], f"B1: 应有 0 part 残留, 实得 {parts}"
    assert finals == [], f"B1: 应有 0 final 残留, 实得 {finals}"
    assert subdirs == [], f"B1: 应有 0 UUID 子目录残留, 实得 {subdirs}"


# B1 + TestClient: 即使 status 不可靠, staging 一定干净
def test_b1_fsync_failure_via_testclient_staging_clean(admin_headers, patch_paths, monkeypatch):
    """B1 (TestClient): TestClient 内部 anyio ExceptionGroup 让 status code 不可靠,
    但 staging 必须完全干净 (核心 B1 目标)."""
    from backend.services import admin_upload as _svc
    from fastapi.testclient import TestClient

    # raise_server_exceptions=False 让 ExceptionGroup 不抛到 pytest, 转 500 response
    client = TestClient(app, raise_server_exceptions=False)

    def _fake_fsync_directory(path):
        raise OSError("simulated directory fsync failure")

    monkeypatch.setattr(_svc, "_fsync_directory", _fake_fsync_directory)

    csv_bytes = "淘宝父订单编号\n456\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    # 不检查 status code (anyio 包装); 仅检查 staging 干净
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    # status 至少是 5xx (anyio 包装后 main general handler 兜底 500)
    assert 500 <= resp.status_code < 600, f"B1 TC: 应 5xx, 实得 {resp.status_code}"

    # 验证 staging 完全干净
    parts = list(patch_paths["staging"].rglob("payload.part"))
    finals = list(patch_paths["staging"].rglob("payload.*"))
    subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert parts == [], f"B1 TC: 应有 0 part 残留, 实得 {parts}"
    assert finals == [], f"B1 TC: 应有 0 final 残留, 实得 {finals}"
    assert subdirs == [], f"B1 TC: 应有 0 UUID 子目录残留, 实得 {subdirs}"


# B2: replace 前失败 → registry 不增记录, payload 被清理
def test_b2_pre_replace_failure_no_registry_record_no_payload(patch_paths, monkeypatch):
    """B2: 模拟 _atomic_write_json 在 replace 前抛异常, 验证:
    - registry 不新增记录
    - 正式 payload 被清理

    直接调 svc.upload 避免 TestClient anyio ExceptionGroup 包装.
    """
    from backend.services import admin_upload as _svc
    import io

    # monkeypatch 整个 _atomic_write_json 模拟"任何调用都抛 OSError"
    # (本测试不关心 backup, 只想验证"写失败时 registry + payload 都被清理")
    def _fake_atomic_write_json(target, data, *, backup_path=None):
        raise OSError("simulated atomic write failure (pre-replace)")

    monkeypatch.setattr(_svc, "_atomic_write_json", _fake_atomic_write_json)

    csv_bytes = "淘宝父订单编号\n100\n".encode("utf-8")
    raised = None
    try:
        _svc.upload(
            business_type="taoke",
            file_obj=io.BytesIO(csv_bytes),
            original_filename="taoke.csv",
            uploaded_by="admin",
        )
    except Exception as exc:
        raised = exc

    assert raised is not None, "B2: replace 前失败应抛错"

    # registry 不应新增记录
    if patch_paths["registry"].exists():
        reg_data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
        assert reg_data["uploads"] == [], f"B2: replace 前失败时 registry 应空, 实得 {reg_data['uploads']}"

    # 正式 payload 不应残留
    all_payloads = list(patch_paths["staging"].rglob("payload.*"))
    assert all_payloads == [], f"B2: payload 应被清理, 实得 {all_payloads}"


# B2: replace 后 fsync 失败 → registry 已 commit + payload 保留 + 同 key 重试不生成第二份
def test_b2_post_replace_failure_keeps_registry_and_payload(patch_paths, monkeypatch):
    """B2: 模拟 _atomic_write_json 在 replace 成功后抛 AtomicWritePostReplaceError, 验证:
    - registry uploads = 1 (committed, replace 已成功)
    - 正式 payload 保留 (committed = True 触发)
    - 同 idempotency key 重试命中老记录, 不生成第二份

    直接调 svc.upload 避开 TestClient anyio ExceptionGroup 包装.
    """
    from backend.services import admin_upload as _svc
    import io

    # 拦截 _atomic_write_json 模拟 replace 已成功 + 抛 AtomicWritePostReplaceError
    # 关键: 区分 "backup 路径" (递归调用, backup_path 参数=None) 跟 "main 路径"
    # (外层调用, backup_path 参数=bak). 我们 trigger 在 main 路径.
    def _fake_atomic_write_json(target, data, *, backup_path=None):
        # main 路径: 模拟 replace 已成功 + 抛 AtomicWritePostReplaceError
        if backup_path is not None and "registry.json" in str(target):
            target.parent.mkdir(parents=True, exist_ok=True)
            import json as _json
            target.write_text(_json.dumps(data, ensure_ascii=False, indent=2))
            raise _svc.AtomicWritePostReplaceError(
                target,
                OSError("simulated post-replace fsync failure"),
            )
        # backup 路径 (递归) 或其他: 跳过
        return None

    monkeypatch.setattr(_svc, "_atomic_write_json", _fake_atomic_write_json)

    csv_bytes = "淘宝父订单编号\n200\n".encode("utf-8")
    raised = None
    try:
        _svc.upload(
            business_type="taoke",
            file_obj=io.BytesIO(csv_bytes),
            original_filename="taoke.csv",
            uploaded_by="admin",
            idempotency_key="b2-post-replace",
        )
    except Exception as exc:
        raised = exc

    # outer 抛 (registry_committed + payload 保留 → outer 不删, 重新 raise)
    assert raised is not None, "B2 post-replace 失败应抛错"

    # registry 应保留 1 条记录 (replace 阶段已成功)
    reg_data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_data["uploads"]) == 1, (
        f"B2: replace 后 fsync 失败时 registry 应有 1 条记录, 实得 {reg_data['uploads']}"
    )

    # 正式 payload 应保留 (committed = True)
    all_payloads = list(patch_paths["staging"].rglob("payload.*"))
    assert len(all_payloads) >= 1, f"B2: payload 应保留, 实得 {all_payloads}"

    # 同 idempotency key 重试 → 命中老记录, 不生成第二份
    payload_dirs_before = list(patch_paths["staging"].iterdir())
    result2 = _svc.upload(
        business_type="taoke",
        file_obj=io.BytesIO(csv_bytes),
        original_filename="taoke2.csv",
        uploaded_by="admin",
        idempotency_key="b2-post-replace",
    )
    assert result2.idempotency_hit is True, "B2: 同 key 重试应命中老记录"
    payload_dirs_after = list(patch_paths["staging"].iterdir())
    assert len(payload_dirs_after) == len(payload_dirs_before), (
        f"B2: 重试不应产生新 staging 目录. before={payload_dirs_before} after={payload_dirs_after}"
    )


# B2 测试 3: backup post-replace 失败 → 主 registry 未写入, committed=False, payload 清空
def test_b2_backup_post_replace_failure_no_main_commit_cleans_payload(patch_paths, monkeypatch):
    """B2 二审加固: 模拟 backup replace 成功后父目录 fsync 失败, 验证:
    - 异常 target.resolve() == backup_path.resolve() (携带正确 backup target)
    - 主 registry 仍只有第一条记录 (没有第二条)
    - 主 registry 不含第二次 Idempotency-Key
    - 第二次 payload 已被删除 (committed=False 触发 outer cleanup)
    - 第二次 UUID staging 子目录已被删除
    - 没有 .part / .tmp 残留
    - 再重试第二次请求时, 可正常创建第二条 registry 记录 (无残留)

    关键: monkeypatch 必须让 _fsync_directory 在 backup 阶段抛, main 阶段不被调用
    (因为 backup 抛 sentinel 后立即 raise, main 不进入). 用 call_count 计数器控制.
    """
    from backend.services import admin_upload as _svc
    import io

    # 1. 正常上传第一条记录 (确保主 registry 已存在, 下次会走 backup 阶段)
    first_csv = "淘宝父订单编号\nfirst\n".encode("utf-8")
    first_result = _svc.upload(
        business_type="taoke",
        file_obj=io.BytesIO(first_csv),
        original_filename="taoke_first.csv",
        uploaded_by="admin",
        idempotency_key="b2-bak-first",
        registry_path=patch_paths["registry"],
        lock_path=patch_paths["lock"],
        backup_path=patch_paths["backup"],
        staging_root=patch_paths["staging"],
    )
    assert first_result.idempotency_hit is False
    first_upload_id = first_result.upload_id

    # 验证第一条 payload 存在 + registry 含 1 条
    first_payload_dir = patch_paths["staging"] / first_upload_id
    assert first_payload_dir.exists() and any(first_payload_dir.iterdir())
    reg_before = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_before["uploads"]) == 1
    assert reg_before["uploads"][0]["idempotency_key"] == "b2-bak-first"

    # 2. 用 call_count 控制 _fsync_directory: staging 1 次正常, backup 1 次抛
    call_count = {"n": 0}
    real_fsync = _svc._fsync_directory

    def _counted_fsync_directory(path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # 第一次调用: staging 目录 fsync → 正常
            return real_fsync(path)
        if call_count["n"] == 2:
            # 第二次调用: backup 目录 fsync → 抛 OSError (被 wrap 成 sentinel)
            raise OSError("simulated backup directory fsync failure")
        # 第三次本应是 main 目录 fsync, 但 backup 抛后 main 不会执行
        raise AssertionError(f"_fsync_directory 第 {call_count['n']} 次意外调用")

    monkeypatch.setattr(_svc, "_fsync_directory", _counted_fsync_directory)

    # 3. 第二次上传: 不同内容 + 不同 hash + 不同 Idempotency-Key
    second_csv = "淘宝父订单编号\nsecond\n".encode("utf-8")
    raised_exc = None
    try:
        _svc.upload(
            business_type="taoke",
            file_obj=io.BytesIO(second_csv),
            original_filename="taoke_second.csv",
            uploaded_by="admin",
            idempotency_key="b2-bak-second",
            registry_path=patch_paths["registry"],
            lock_path=patch_paths["lock"],
            backup_path=patch_paths["backup"],
            staging_root=patch_paths["staging"],
        )
    except Exception as exc:
        raised_exc = exc

    # 4. 必须捕获 AtomicWritePostReplaceError + target 是 backup_path (不是 registry_path)
    assert isinstance(raised_exc, _svc.AtomicWritePostReplaceError), (
        f"B2 backup post-replace: 应抛 AtomicWritePostReplaceError, 实得 {type(raised_exc).__name__}: {raised_exc}"
    )
    assert raised_exc.target.resolve() == patch_paths["backup"].resolve(), (
        f"B2: AtomicWritePostReplaceError.target 应等于 backup_path.resolve(), "
        f"实得 {raised_exc.target.resolve()} vs 期望 {patch_paths['backup'].resolve()}"
    )

    # 5. 主 registry 仍只有第一条记录 (第二条未写入)
    reg_after = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_after["uploads"]) == 1, (
        f"B2 backup 失败时主 registry 应只有第一条, 实得 {len(reg_after['uploads'])} 条"
    )
    assert all(
        e["idempotency_key"] != "b2-bak-second" for e in reg_after["uploads"]
    ), "B2 backup 失败时主 registry 不应含第二条 idempotency_key"

    # 6. 第二次 staging UUID 子目录 + payload 都被清理 (committed=False 触发 outer cleanup)
    all_subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert len(all_subdirs) == 1, (
        f"B2 backup 失败后 staging 应只有第一条子目录, 实得 {all_subdirs}"
    )
    assert all_subdirs[0].name == first_upload_id

    # 7. 没有 .part / .upload_registry.*.tmp 残留
    parts = list(patch_paths["staging"].rglob("*.part"))
    tmp_files = list(patch_paths["staging"].rglob(".upload_registry.*.tmp"))
    assert parts == [], f"B2: 应无 .part 残留, 实得 {parts}"
    assert tmp_files == [], f"B2: 应无 .upload_registry.*.tmp 残留, 实得 {tmp_files}"

    # 8. _fsync_directory 恰好被调用 2 次 (staging + backup, main 未进入)
    assert call_count["n"] == 2, (
        f"B2: _fsync_directory 应调用 2 次 (staging + backup), 实得 {call_count['n']} 次"
    )

    # 9. 重试第二次请求 (不用 monkeypatch) 应能正常创建第二条记录
    monkeypatch.undo()  # 恢复真实 _fsync_directory
    retry_result = _svc.upload(
        business_type="taoke",
        file_obj=io.BytesIO(second_csv),
        original_filename="taoke_second.csv",
        uploaded_by="admin",
        idempotency_key="b2-bak-second",
        registry_path=patch_paths["registry"],
        lock_path=patch_paths["lock"],
        backup_path=patch_paths["backup"],
        staging_root=patch_paths["staging"],
    )
    assert retry_result.idempotency_hit is False
    assert retry_result.upload_id != first_upload_id
    reg_final = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_final["uploads"]) == 2
    keys = {e["idempotency_key"] for e in reg_final["uploads"]}
    assert keys == {"b2-bak-first", "b2-bak-second"}
    # 两条 payload 都在 staging (一一对应, 无孤儿)
    final_subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert len(final_subdirs) == 2


# B2 测试 4: 模拟主 registry 真实 replace 后 fsync 失败 (用 _fsync_directory 真实调用链)
def test_b2_main_post_replace_real_fsync_failure_keeps_payload(patch_paths, monkeypatch):
    """B2 二审加固: 不整体伪造 _atomic_write_json, 用 _fsync_directory monkeypatch 让
    '主 registry replace 后父目录 fsync' 失败. 让真实 _atomic_write_json() 跑完
    tempfile + json.dump + file fsync + os.replace, 然后 _fsync_directory 抛.

    验证:
    - AtomicWritePostReplaceError.target == registry_path
    - registry 含新记录 (replace 已成功)
    - payload 保留
    - registry staged_path 指向该 payload
    - 同 Idempotency-Key 重试 idempotency_hit=True
    - staging 不增加第二份持久 payload
    """
    from backend.services import admin_upload as _svc
    import io

    # 1. 控制 _fsync_directory: staging 正常 + 主 registry 抛
    real_fsync = _svc._fsync_directory
    call_count = {"n": 0}

    def _controlled_fsync(path):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # staging 目录 fsync → 正常
            return real_fsync(path)
        if call_count["n"] == 2:
            # 主 registry 父目录 fsync → 抛 OSError (被 wrap 成 sentinel)
            raise OSError("simulated main registry directory fsync failure")
        raise AssertionError(f"_fsync_directory 第 {call_count['n']} 次意外调用")

    monkeypatch.setattr(_svc, "_fsync_directory", _controlled_fsync)

    csv_bytes = "淘宝父订单编号\nmain-real\n".encode("utf-8")
    raised_exc = None
    try:
        _svc.upload(
            business_type="taoke",
            file_obj=io.BytesIO(csv_bytes),
            original_filename="taoke_main.csv",
            uploaded_by="admin",
            idempotency_key="b2-main-real",
            registry_path=patch_paths["registry"],
            lock_path=patch_paths["lock"],
            backup_path=patch_paths["backup"],
            staging_root=patch_paths["staging"],
        )
    except Exception as exc:
        raised_exc = exc

    # 2. 异常 target == registry_path
    assert isinstance(raised_exc, _svc.AtomicWritePostReplaceError)
    assert raised_exc.target.resolve() == patch_paths["registry"].resolve(), (
        f"B2 main post-replace: exc.target 应等于 registry_path, "
        f"实得 {raised_exc.target.resolve()} vs {patch_paths['registry'].resolve()}"
    )

    # 3. registry 含新记录 (replace 已成功, committed=True 触发)
    reg_data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
    assert len(reg_data["uploads"]) == 1
    entry = reg_data["uploads"][0]
    assert entry["idempotency_key"] == "b2-main-real"

    # 4. payload 保留
    all_payloads = list(patch_paths["staging"].rglob("payload.*"))
    assert len(all_payloads) == 1, f"B2 main: payload 应保留, 实得 {all_payloads}"

    # 5. registry staged_path 指向该 payload
    upload_id = entry["upload_id"]
    expected_payload = patch_paths["staging"] / upload_id / "payload.csv"
    assert expected_payload.exists()
    assert entry["staged_path"].endswith(f"{upload_id}/payload.csv"), (
        f"B2 main: registry staged_path 应指向该 payload, 实得 {entry['staged_path']}"
    )

    # 6. 同 Idempotency-Key 重试 idempotency_hit=True
    monkeypatch.undo()  # 恢复真实 _fsync_directory
    payload_dirs_before = {d.name for d in patch_paths["staging"].iterdir() if d.is_dir()}
    retry_result = _svc.upload(
        business_type="taoke",
        file_obj=io.BytesIO(csv_bytes),
        original_filename="taoke_main_retry.csv",
        uploaded_by="admin",
        idempotency_key="b2-main-real",
        registry_path=patch_paths["registry"],
        lock_path=patch_paths["lock"],
        backup_path=patch_paths["backup"],
        staging_root=patch_paths["staging"],
    )
    assert retry_result.idempotency_hit is True, "B2 main: 同 key 重试应命中老记录"
    payload_dirs_after = {d.name for d in patch_paths["staging"].iterdir() if d.is_dir()}
    assert payload_dirs_before == payload_dirs_after, (
        f"B2 main: 重试不应产生新 staging 目录. before={payload_dirs_before} after={payload_dirs_after}"
    )


# B3: SPU mapping preflight 跟 ETL loader 对齐
def test_b3_spu_mapping_accepts_integer_id(client, admin_headers, patch_paths):
    """B3: SPU 单行 + 整数 ID + 11 列 → 201 (headerless)."""
    # 11 列 + 1 行整数 ID
    spu_csv = "1,a,b,c,d,e,f,g,h,i,j\n".encode("utf-8")
    files = {"file": ("spu.csv", spu_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "spu-mapping"},
        files=files,
    )
    assert resp.status_code == 201, f"SPU 整数 ID 应 201, 实得 {resp.status_code} {resp.text}"


def test_b3_spu_mapping_accepts_decimal_id(client, admin_headers, patch_paths):
    """B3: SPU 123.0 ID + 11 列 → 201 (跟 sources.py 正则 ^\\d+\\.?\\d*$ 一致)."""
    spu_csv = "123.0,a,b,c,d,e,f,g,h,i,j\n".encode("utf-8")
    files = {"file": ("spu.csv", spu_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "spu-mapping"},
        files=files,
    )
    assert resp.status_code == 201, f"SPU 小数 ID 应 201, 实得 {resp.status_code} {resp.text}"


def test_b3_spu_mapping_rejects_too_few_columns(client, admin_headers, patch_paths):
    """B3: 少于 11 列 → 422."""
    spu_csv = "1,a,b,c,d,e,f,g,h,i\n".encode("utf-8")  # 10 列
    files = {"file": ("spu.csv", spu_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "spu-mapping"},
        files=files,
    )
    assert resp.status_code == 422, f"少于 11 列应 422, 实得 {resp.status_code}"
    assert "列数" in resp.json()["detail"]["message"]


def test_b3_spu_mapping_rejects_no_data_rows(client, admin_headers, patch_paths):
    """B3: 空文件 → 422."""
    files = {"file": ("spu.csv", b"", "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "spu-mapping"},
        files=files,
    )
    assert resp.status_code in (400, 422), f"空文件应 4xx, 实得 {resp.status_code}"


def test_b3_spu_mapping_rejects_non_numeric_product_id(client, admin_headers, patch_paths):
    """B3 二审加固: 11 列 + 1 行数据 + 第 1 列非合法数字 → 422 VALIDATION_FAILED.

    Codex Stage 4 二审加固: 之前 B3 测试只覆盖整数 ID / 123.0 / 少列 / 空文件,
    缺"11 列 + 数据行 + 第 1 列全部非数字"的关键分支 (跟 sources.py:94 正则
    ^\\d+\\.?\\d*$ 不匹配 → ValidationFailed).

    注意: 不要用 0 字节文件 (0 字节会在 service 层先抛 EMPTY_FILE 400,
    走不到 _validate_spu_mapping 的 product_id 分支).
    """
    # 11 列 + 1 行非数字 ID
    spu_csv = (
        "商品ID,a,b,c,d,e,f,g,h,i,j\n"
        "not-a-product-id,a,b,c,d,e,f,g,h,i,j\n"
    ).encode("utf-8")
    files = {"file": ("spu.csv", spu_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "spu-mapping"},
        files=files,
    )
    # 422 VALIDATION_FAILED + message 含 "product_id" (跟 sources.py 1:1 stable)
    assert resp.status_code == 422, (
        f"非数字 product_id 应 422, 实得 {resp.status_code} {resp.text}"
    )
    detail = resp.json()["detail"]
    assert detail["code"] == "VALIDATION_FAILED"
    assert "product_id" in detail["message"], (
        f"422 message 应提到 product_id, 实得: {detail['message']}"
    )

    # staging payload + UUID 目录都应被清理
    all_payloads = list(patch_paths["staging"].rglob("payload.*"))
    assert all_payloads == [], f"422 后 staging 应清 payload, 实得 {all_payloads}"
    subdirs = [d for d in patch_paths["staging"].iterdir() if d.is_dir()]
    assert subdirs == [], f"422 后 staging 应清 UUID 目录, 实得 {subdirs}"

    # registry 不应有新记录
    if patch_paths["registry"].exists():
        reg_data = json.loads(patch_paths["registry"].read_text(encoding="utf-8"))
        assert reg_data["uploads"] == [], (
            f"422 后 registry 应空, 实得 {reg_data['uploads']}"
        )


def test_b3_spu_mapping_rejects_all_non_numeric_product_ids(client, admin_headers, patch_paths):
    """B3 二审加固: 11 列 + 多行数据 + 全部非数字 → 422."""
    spu_csv = (
        "商品ID,a,b,c,d,e,f,g,h,i,j\n"
        "abc,1,2,3,4,5,6,7,8,9,10\n"
        "xyz,11,22,33,44,55,66,77,88,99,110\n"
    ).encode("utf-8")
    files = {"file": ("spu.csv", spu_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "spu-mapping"},
        files=files,
    )
    assert resp.status_code == 422, (
        f"全部非数字 product_id 应 422, 实得 {resp.status_code} {resp.text}"
    )


# B5: channel-rules 走 staged path 真实校验 (不是被 _try_csv 提前 reject)
def test_b5_channel_rules_validator_uses_staged_path(client, admin_headers, patch_paths, monkeypatch):
    """B5: 构造可被 _try_csv 解析但 channel rules schema 错误的输入, 验证
    load_channel_rules 收到 staged path, 不是 active target.

    Codex Stage 4 二审加固: 不只断言 "/staging/" in str(called_path) (弱, 可能误命中
    巧合含 staging 字符串的路径). 改用精确断言:
    1. monkeypatch active source 到唯一 fake path
    2. 验证 svc.get_source('channel-rules').target_path == fake
    3. spy 捕获 channel_file, 断言:
       - 父目录的父目录 (即 UUID 子目录的父目录) == staging_root
       - called_path.resolve() != fake.resolve() (不读 active target)
       - loader 调用期间 staged payload 存在 + bytes 等于本次上传内容
    4. 调用结束返回 422 后 staging 被清理
    5. active target 字节不变
    """
    from backend import config as cfg
    from backend.services import admin_upload as _svc
    from scripts.etl import sources as _sources

    # 1. monkeypatch active source 到唯一 fake path
    fake_active = patch_paths["staging"].parent / "channel_rules_active_uniq.csv"
    fake_active.parent.mkdir(parents=True, exist_ok=True)
    original_active_bytes = b"\xef\xbb\xbf\xe5\x85\xb3\xe9\x94\xae\xe8\xaf\x8d,\xe6\xb8\xa0\xe9\x81\x93\n\xe6\x8a\x96\xe9\x9f\xb3,\xe6\x8a\x96\xe9\x9f\xb3\xe6\xb8\xa0\xe9\x81\x93\n"
    fake_active.write_bytes(original_active_bytes)

    monkeypatch.setattr(cfg, "CHANNEL_RULES_SOURCE", fake_active)

    # 2. 验证 monkeypatch 生效
    src = _svc.get_source("channel-rules")
    assert src is not None
    assert src.target_path.resolve() == fake_active.resolve(), (
        f"monkeypatch 后 svc.get_source('channel-rules').target_path 应等于 fake_active, "
        f"实得 {src.target_path.resolve()} vs 期望 {fake_active.resolve()}"
    )

    # 3. spy 捕获 channel_file, 包括 exists_during_call + bytes_during_call
    captured = {}

    def _spy_load_channel_rules(channel_file=None):
        path = Path(channel_file)
        captured["path"] = path
        captured["exists_during_call"] = path.exists()
        try:
            captured["bytes_during_call"] = path.read_bytes()
        except OSError as exc:
            captured["bytes_during_call"] = f"<read failed: {exc}>"
        # 模拟解析错误 → (None, None) → 0 条规则 fail-closed → 422
        return None, None

    monkeypatch.setattr(_sources, "load_channel_rules", _spy_load_channel_rules)
    monkeypatch.setattr(
        "backend.services.admin_upload.load_channel_rules",
        _spy_load_channel_rules,
        raising=False,
    )

    # 4. 上传有效 staged CSV (但 channel rules schema 错误)
    bad_csv = "wrong_a,wrong_b,wrong_c\n1,2,3\n".encode("utf-8")
    files = {"file": ("channel.csv", bad_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "channel-rules"},
        files=files,
    )
    # 422 (load_channel_rules 返 (None, None) → 0 条规则 fail-closed)
    assert resp.status_code == 422, f"channel-rules 错误应 422, 实得 {resp.status_code} {resp.text}"
    assert resp.json()["detail"]["code"] == "VALIDATION_FAILED"

    # 5. spy 必须被调用 1 次, 精确断言 called_path 是 staged (非 active target)
    assert "path" in captured, f"spy 未被调用, captured={captured}"
    called_path = captured["path"]
    assert called_path.name == "payload.csv", (
        f"应传 payload.csv, 实得 {called_path.name}"
    )
    # parent.parent == staging_root (call_path 是 UUID/payload.csv, parent = UUID dir, parent.parent = staging_root)
    assert called_path.parent.parent.resolve() == patch_paths["staging"].resolve(), (
        f"called_path.parent.parent 应等于 staging_root, "
        f"实得 {called_path.parent.parent.resolve()} vs {patch_paths['staging'].resolve()}"
    )
    # 不应是 fake active target
    assert called_path.resolve() != fake_active.resolve(), (
        f"loader 不应被传 active target, 实得 {called_path.resolve()}"
    )

    # 6. loader 调用期间 staged payload 确实存在 + bytes 等于本次上传内容
    assert captured.get("exists_during_call") is True, (
        f"loader 调用期间 staged payload 应存在, 实得 exists_during_call={captured.get('exists_during_call')}"
    )
    assert captured.get("bytes_during_call") == bad_csv, (
        f"loader 调用期间 staged payload bytes 应等于本次上传内容, "
        f"实得 {captured.get('bytes_during_call')!r} vs 期望 {bad_csv!r}"
    )

    # 7. active target 字节级不变 (不被改写)
    assert fake_active.read_bytes() == original_active_bytes, (
        "B5: fake active target 字节不应被改写"
    )

    # 8. response 不含 traceback + 不含原始异常消息
    assert "Traceback" not in resp.text
    assert "internal" not in resp.text.lower()  # 不泄露 loader 内部细节


def test_b5_channel_rules_loader_exception_returns_422_no_traceback(client, admin_headers, patch_paths, monkeypatch):
    """B5: loader 抛异常 → 422 VALIDATION_FAILED, 不泄露 traceback (不 500).

    Codex Stage 4 二审加固: 同时验证 loader 抛异常时, 异常消息 type 包含但不
    含原始异常 message (防止泄露 loader 内部细节).
    """
    from scripts.etl import sources as _sources

    def _exploding_loader(channel_file=None):
        raise RuntimeError("internal loader error should not leak")

    monkeypatch.setattr(_sources, "load_channel_rules", _exploding_loader)
    monkeypatch.setattr(
        "backend.services.admin_upload.load_channel_rules",
        _exploding_loader,
        raising=False,
    )

    good_csv = "关键词,渠道\ntest,测试渠道\n".encode("utf-8")
    files = {"file": ("channel.csv", good_csv, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "channel-rules"},
        files=files,
    )
    assert resp.status_code == 422, f"loader 异常应 422, 实得 {resp.status_code} {resp.text}"
    assert resp.json()["detail"]["code"] == "VALIDATION_FAILED"
    # 验证响应不泄露 traceback (HTTPException detail 字符串不含 "Traceback")
    assert "Traceback" not in resp.text, "响应不应泄露 Python traceback"
    # 验证响应不包含 loader 抛出的原始异常消息 (防内部细节泄露)
    assert "internal loader error should not leak" not in resp.text, (
        "响应不应包含 loader 抛出的原始异常消息"
    )


# B6: registry 严格结构校验
def test_b6_registry_uploads_null_raises(patch_paths):
    """B6: uploads=null → _validate_registry_data 抛 ValueError."""
    from backend.services.admin_upload import _validate_registry_data
    with pytest.raises(ValueError, match="uploads 不是 list"):
        _validate_registry_data({"uploads": None})


def test_b6_registry_uploads_dict_raises(patch_paths):
    """B6: uploads={} (dict 不是 list) → ValueError."""
    from backend.services.admin_upload import _validate_registry_data
    with pytest.raises(ValueError, match="uploads 不是 list"):
        _validate_registry_data({"uploads": {}})


def test_b6_registry_scalar_entry_raises(patch_paths):
    """B6: uploads 含 scalar (string/int) → ValueError."""
    from backend.services.admin_upload import _validate_registry_data
    with pytest.raises(ValueError, match="不是 dict"):
        _validate_registry_data({"uploads": ["scalar_entry"]})


def test_b6_registry_missing_required_field_raises(patch_paths):
    """B6: entry 缺必需字段 → ValueError (校验顺序: original_filename 先)."""
    from backend.services.admin_upload import _validate_registry_data
    incomplete_entry = {
        "upload_id": "x", "business_type": "taoke",
        # missing sha256 / uploaded_by / uploaded_at / status / etc
    }
    # _validate_registry_data 会先校验 original_filename 缺失, 抛 original_filename 不是 str
    with pytest.raises(ValueError, match="original_filename"):
        _validate_registry_data({"uploads": [incomplete_entry]})


def test_b6_registry_recovery_when_both_corrupt(admin_headers, patch_paths):
    """B6: 主+backup 都坏 → 受控错误 (registry_corrupt 500).
    TestClient raise_server_exceptions=False 避开 anyio ExceptionGroup."""
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)
    patch_paths["registry"].write_text("not json")
    patch_paths["backup"].write_text("also not json")
    resp = client.get("/api/v1/admin/uploads", headers=admin_headers)
    # 500 (RegistryCorrupt → router 映射)
    assert resp.status_code == 500, f"主+backup 都坏应 500, 实得 {resp.status_code}"


def test_b6_registry_recovery_main_corrupt_backup_ok(client, admin_headers, patch_paths):
    """B6: 主坏 + backup 正常 → 200 恢复 (走 LOCK_EX recovery)."""
    # 先正常 upload 1 条 (产生 backup)
    csv_bytes = "淘宝父订单编号\n1\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    # 第二次 upload 触发 backup 备份
    csv_bytes2 = "淘宝父订单编号\n2\n".encode("utf-8")
    files2 = {"file": ("taoke2.csv", csv_bytes2, "text/csv")}
    client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files2,
    )
    # 损坏主
    patch_paths["registry"].write_text("CORRUPT{{{")
    # GET 应恢复 (从 bak)
    resp = client.get("/api/v1/admin/uploads", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_b6_multi_reader_concurrent_corrupt_recovery(patch_paths):
    """B6 二审加固: 多个 reader 同时发现主 registry 损坏时, 只有一个 reader
    持 LOCK_EX 恢复, 其他 reader 随后读到恢复后的主文件 (threading 同进程).

    流程:
    1. 准备结构合法的 backup registry (至少 1 条完整 upload entry)
    2. 主 registry 写入损坏 JSON
    3. 用 threading.Barrier 同步启动 5 个 reader, 全部调 svc.list_uploads
    4. 收集结果 + 异常

    断言:
    - 5 个 reader 全部成功 (无异常)
    - 5 个 reader 都读到同一 total
    - 主 registry 最终是合法 JSON + 通过 _validate_registry_data
    - 主 registry 内容跟 backup 的 uploads 一致
    - 无 .upload_registry.*.tmp 残留
    - backup 仍是合法 JSON
    - 锁文件允许存在
    - 无丢记录 / 重复记录
    """
    from backend.services import admin_upload as _svc
    from backend.services.admin_upload import _validate_registry_data
    import threading

    # 1. 准备结构合法的 backup registry
    backup_entry = {
        "upload_id": "u_backup_001",
        "business_type": "taoke",
        "original_filename": "backup.csv",
        "extension": ".csv",
        "staged_path": "data/processed/admin_uploads/staging/u_backup_001/payload.csv",
        "size_bytes": 100,
        "sha256": "a" * 64,
        "uploaded_by": "admin",
        "uploaded_at": "2026-07-16T00:00:00+00:00",
        "status": "staged",
        "validation": {
            "validator": "csv-utf8",
            "valid": True,
            "detected_format": "encoding=utf-8;cols=2",
            "row_sample_count": 1,
            "warnings": [],
        },
        "future_post_actions": [],
        "idempotency_key": "b6-multi-reader",
    }
    backup_data = {"schema_version": 1, "uploads": [backup_entry]}
    patch_paths["backup"].write_text(json.dumps(backup_data, ensure_ascii=False, indent=2))

    # 2. 主 registry 写入损坏 JSON
    patch_paths["registry"].write_text("this is corrupt json {{{ not parseable")

    # 3. 同步启动 5 个 reader
    barrier = threading.Barrier(5)
    results = []
    errors = []

    def reader(idx: int):
        try:
            # 等所有 reader 同步到达 barrier 后并发跑
            barrier.wait(timeout=10)
            items, total = _svc.list_uploads(
                registry_path=patch_paths["registry"],
                lock_path=patch_paths["lock"],
                backup_path=patch_paths["backup"],
            )
            results.append((idx, items, total))
        except Exception as exc:  # noqa: BLE001
            errors.append((idx, exc))

    threads = [threading.Thread(target=reader, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    # 4. 全部成功 + 同一 total
    assert not errors, f"5 个 reader 应无异常, 实得 errors={errors}"
    assert len(results) == 5, f"5 个 reader 应全部返回结果, 实得 {len(results)}"
    totals = {total for _, _, total in results}
    assert totals == {1}, f"5 个 reader 应都读到 1 条, 实得 totals={totals}"

    # 5. 主 registry 最终是合法 JSON + 通过 _validate_registry_data
    main_text = patch_paths["registry"].read_text(encoding="utf-8")
    main_data = json.loads(main_text)  # 合法 JSON 解析不抛
    _validate_registry_data(main_data)  # 严格校验不抛

    # 6. 主 registry 内容跟 backup 的 uploads 一致
    assert main_data.get("uploads") == backup_data["uploads"], (
        f"主 registry 恢复后内容应跟 backup 一致, main={main_data['uploads']} backup={backup_data['uploads']}"
    )

    # 7. 无 .upload_registry.*.tmp 残留 (recovery 走 LOCK_EX 单飞, 不留 tmp)
    tmp_files = list(patch_paths["registry"].parent.glob(".upload_registry.*.tmp"))
    assert tmp_files == [], f"recovery 后应无 tmp 残留, 实得 {tmp_files}"

    # 8. backup 仍是合法 JSON
    bak_text = patch_paths["backup"].read_text(encoding="utf-8")
    bak_data = json.loads(bak_text)
    _validate_registry_data(bak_data)

    # 9. 无丢记录 / 重复记录 (主 uploads == backup uploads)
    assert len(main_data["uploads"]) == 1
    assert main_data["uploads"][0]["upload_id"] == "u_backup_001"

    # 10. 锁文件允许存在 (fcntl.flock LOCK_UN 后留 lock 文件)
    assert patch_paths["lock"].exists(), "lock 文件应保留 (fcntl 风格)"


# L1: Idempotency-Key 长度 + whitespace 限制
def test_l1_idempotency_key_max_length_128_passes(client, admin_headers, patch_paths):
    """L1: 128 字符 Idempotency-Key 通过."""
    key_128 = "a" * 128
    headers = {**admin_headers, "Idempotency-Key": key_128}
    csv_bytes = "淘宝父订单编号\n1\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201, f"128 字符 key 应 201, 实得 {resp.status_code} {resp.text}"


def test_l1_idempotency_key_129_chars_rejected(client, admin_headers, patch_paths):
    """L1: 129 字符 Idempotency-Key → 400 IDEMPOTENCY_KEY_INVALID."""
    key_129 = "a" * 129
    headers = {**admin_headers, "Idempotency-Key": key_129}
    csv_bytes = "淘宝父订单编号\n1\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 400, f"129 字符 key 应 400, 实得 {resp.status_code}"
    assert resp.json()["detail"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_l1_idempotency_key_whitespace_only_rejected(client, admin_headers, patch_paths):
    """L1: whitespace-only Idempotency-Key → 400 IDEMPOTENCY_KEY_INVALID."""
    headers = {**admin_headers, "Idempotency-Key": "   "}
    csv_bytes = "淘宝父订单编号\n1\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 400, f"whitespace-only key 应 400, 实得 {resp.status_code}"
    assert resp.json()["detail"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_l1_idempotency_key_missing_maintains_api_contract(client, admin_headers, patch_paths):
    """L1: 不带 Idempotency-Key (缺失) 维持现有行为 → 201."""
    csv_bytes = "淘宝父订单编号\n1\n".encode("utf-8")
    files = {"file": ("taoke.csv", csv_bytes, "text/csv")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "taoke"},
        files=files,
    )
    assert resp.status_code == 201


# L3: empty XLSX 422
def test_l3_empty_xlsx_returns_422(client, admin_headers, patch_paths):
    """L3: xlsx 是有效格式但只有空 sheet → 422."""
    from openpyxl import Workbook
    wb = Workbook()
    # 不加任何数据行, 只有默认空 sheet
    import io
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    files = {"file": ("shop.xlsx", buf.read(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    resp = client.post(
        "/api/v1/admin/upload",
        headers=admin_headers,
        data={"business_type": "shop"},
        files=files,
    )
    assert resp.status_code == 422, f"空 XLSX 应 422, 实得 {resp.status_code} {resp.text}"


# L3: is_admin 三路径一致 (真实 E2E: login → /me → login-request claim)
def test_l3_is_admin_consistent_across_login_me_claim(client):
    """L3: 真实 E2E 覆盖 login / /me / login-request claim 三条 HTTP 路径,
    is_admin 字段一致 (admin=True / fqsw=False).

    Codex Stage 4 二审加固: 之前只覆盖 login + /me, 缺 login-request claim 真实流程.
    现有 test_login_request_claim_response_includes_is_admin 只检查 Pydantic schema 字段,
    不跑 claim HTTP. 现在用真实 E2E: A 登录 → B 申请 → A 批准 → B claim, 验证
    B claim response 的 is_admin 字段跟 A 目标账号一致.
    """
    from backend.routers.auth import is_admin_username

    # ==== admin 账号 E2E ====
    # 1. A 登录 admin
    admin_a_resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "123456"})
    assert admin_a_resp.status_code == 200
    admin_a_token = admin_a_resp.json()["token"]
    assert admin_a_resp.json()["is_admin"] is True

    # 2. /me
    me_admin_resp = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )
    assert me_admin_resp.status_code == 200
    assert me_admin_resp.json()["is_admin"] is True

    # 3. B 用密码申请登录 admin (admin 当前 active → 走申请路径)
    req_resp = client.post(
        "/api/v1/auth/login-request",
        json={"username": "admin", "password": "123456"},
    )
    assert req_resp.status_code == 200, (
        f"申请登录 admin 应 200, 实得 {req_resp.status_code} {req_resp.text}"
    )
    claim_token = req_resp.json()["claim_token"]
    request_id = req_resp.json()["request_id"]

    # 4. A 查待处理申请 → 批准
    pending_resp = client.get(
        "/api/v1/auth/login-requests/pending",
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )
    assert pending_resp.status_code == 200
    pending_list = pending_resp.json()["pending"]
    assert len(pending_list) == 1
    assert pending_list[0]["request_id"] == request_id

    approve_resp = client.post(
        f"/api/v1/auth/login-request/{request_id}/approve",
        headers={"Authorization": f"Bearer {admin_a_token}"},
    )
    assert approve_resp.status_code == 200, f"approve 应 200, 实得 {approve_resp.status_code}"

    # 5. B claim → 拿 token + is_admin
    claim_resp = client.post(
        f"/api/v1/auth/login-request/{request_id}/claim",
        headers={"X-Login-Claim": claim_token},
    )
    assert claim_resp.status_code == 200, (
        f"claim 应 200, 实得 {claim_resp.status_code} {claim_resp.text}"
    )
    claim_json = claim_resp.json()
    assert claim_json["username"] == "admin"
    assert claim_json["is_admin"] is True
    # 用 is_admin_username 验证: claim 的 is_admin 必须跟该 username 调用 is_admin_username 一致
    assert is_admin_username(claim_json["username"]) == claim_json["is_admin"]

    # ==== fqsw (non-admin) E2E ====
    # 用新 client (隔离 ACTIVE_TOKENS, 模拟独立会话, 避免 admin 仍 active → 409)
    from fastapi.testclient import TestClient as _TC
    from backend.main import app as _app
    fqsw_client = _TC(_app)

    # 1. A 登录 fqsw
    fqsw_a_resp = fqsw_client.post("/api/v1/auth/login", json={"username": "fqsw", "password": "fqsw888"})
    assert fqsw_a_resp.status_code == 200
    fqsw_a_token = fqsw_a_resp.json()["token"]
    assert fqsw_a_resp.json()["is_admin"] is False

    # 2. /me
    me_fqsw_resp = fqsw_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {fqsw_a_token}"},
    )
    assert me_fqsw_resp.status_code == 200
    assert me_fqsw_resp.json()["is_admin"] is False

    # 3. B 申请登录 fqsw
    fqsw_req_resp = fqsw_client.post(
        "/api/v1/auth/login-request",
        json={"username": "fqsw", "password": "fqsw888"},
    )
    assert fqsw_req_resp.status_code == 200, (
        f"申请登录 fqsw 应 200, 实得 {fqsw_req_resp.status_code} {fqsw_req_resp.text}"
    )
    fqsw_claim_token = fqsw_req_resp.json()["claim_token"]
    fqsw_request_id = fqsw_req_resp.json()["request_id"]

    # 4. A 批准
    fqsw_approve_resp = fqsw_client.post(
        f"/api/v1/auth/login-request/{fqsw_request_id}/approve",
        headers={"Authorization": f"Bearer {fqsw_a_token}"},
    )
    assert fqsw_approve_resp.status_code == 200

    # 5. B claim
    fqsw_claim_resp = fqsw_client.post(
        f"/api/v1/auth/login-request/{fqsw_request_id}/claim",
        headers={"X-Login-Claim": fqsw_claim_token},
    )
    assert fqsw_claim_resp.status_code == 200, (
        f"fqsw claim 应 200, 实得 {fqsw_claim_resp.status_code} {fqsw_claim_resp.text}"
    )
    fqsw_claim_json = fqsw_claim_resp.json()
    assert fqsw_claim_json["username"] == "fqsw"
    assert fqsw_claim_json["is_admin"] is False
    assert is_admin_username(fqsw_claim_json["username"]) == fqsw_claim_json["is_admin"]


# L3 backward-compat: schema 字段存在性 (Codex Stage 4 加固, 跟 v3 test 1:1 stable 沿用)
def test_l3_login_request_claim_response_schema_has_is_admin():
    """Codex Stage 4 加固: Pydantic ClaimRequestOut schema 必含 is_admin 字段 (跟 L4.85.1 1:1 stable)."""
    from backend.routers.login_request import ClaimRequestOut
    fields = ClaimRequestOut.model_fields.keys()
    assert "is_admin" in fields, f"ClaimRequestOut 缺 is_admin: {fields}"
    assert "token" in fields
    assert "username" in fields


# L3: OpenAPI $ref 精确断言 (UploadResponse / UploadConfigResponse / UploadRecordOut)
def test_l3_openapi_admin_schemas_have_correct_refs(client):
    """L3: OpenAPI 6 个 schema 必存在 + 4 个精确 $ref 必指向正确 schema.

    Codex Stage 4 二审加固: 之前只检查 schema 是否包含任意 ref 键, 即使指向错误
    schema 也会通过. 改用 helper 精确断言每个 path+method+status 的
    $ref == 期望 schema.
    """
    def _response_schema_ref(spec, path, method, status):
        """精确提取 path+method+status 的 response $ref (返回字符串 ref name 或 None)."""
        ref = spec["paths"][path][method]["responses"][str(status)]["content"]["application/json"]["schema"].get("$ref")
        return ref

    spec = client.get("/openapi.json").json()
    schemas = spec["components"]["schemas"]

    # 6 个 admin schema 必存在
    for schema_name in (
        "UploadConfigResponse",
        "UploadSourcePublic",
        "UploadValidationResult",
        "UploadRecordOut",
        "UploadResponse",
        "UploadListResponse",
    ):
        assert schema_name in schemas, f"OpenAPI schemas 缺 {schema_name}"

    # 4 个精确 $ref 断言
    assert _response_schema_ref(spec, "/api/v1/admin/upload-config", "get", 200) == \
        "#/components/schemas/UploadConfigResponse", (
        f"upload-config 200 应指向 UploadConfigResponse, "
        f"实得 {_response_schema_ref(spec, '/api/v1/admin/upload-config', 'get', 200)}"
    )
    assert _response_schema_ref(spec, "/api/v1/admin/uploads", "get", 200) == \
        "#/components/schemas/UploadListResponse", (
        f"uploads 200 应指向 UploadListResponse, "
        f"实得 {_response_schema_ref(spec, '/api/v1/admin/uploads', 'get', 200)}"
    )
    assert _response_schema_ref(spec, "/api/v1/admin/upload", "post", 200) == \
        "#/components/schemas/UploadResponse", (
        f"upload 200 应指向 UploadResponse, "
        f"实得 {_response_schema_ref(spec, '/api/v1/admin/upload', 'post', 200)}"
    )
    assert _response_schema_ref(spec, "/api/v1/admin/upload", "post", 201) == \
        "#/components/schemas/UploadResponse", (
        f"upload 201 应指向 UploadResponse, "
        f"实得 {_response_schema_ref(spec, '/api/v1/admin/upload', 'post', 201)}"
    )
