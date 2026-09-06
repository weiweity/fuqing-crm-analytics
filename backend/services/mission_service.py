"""Deterministic CEO Mission service for the synthetic public demo.

The service is fail-closed: it is disabled by default and has no fallback to the
private CRM DuckDB configured by the legacy application.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb

from scripts.synthetic.generate_hackathon_dataset import (
    compute_dataset_content_sha256,
    validate_synthetic_database,
)


SHA256_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")
MISSION_STATES = (
    "DISCOVERED",
    "EVIDENCE_READY",
    "AWAITING_APPROVAL",
    "APPROVED",
    "WAITING_MEASUREMENT",
)


class MissionServiceError(RuntimeError):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _parse_version(value: str) -> int:
    normalized = value.strip().removeprefix("W/").strip('"')
    try:
        version = int(normalized)
    except ValueError as exc:
        raise MissionServiceError(400, "If-Match 必须是 Mission 的整数版本号") from exc
    if version < 1:
        raise MissionServiceError(400, "If-Match 版本号无效")
    return version


class MissionService:
    """Read synthetic evidence and persist only approval/export control state."""

    def __init__(self, analysis_db: Path, control_db: Path, export_dir: Path):
        self.analysis_db = analysis_db.resolve()
        self.manifest_path = self.analysis_db.with_suffix(".manifest.json")
        self.control_db = control_db.resolve()
        self.export_dir = export_dir.resolve()
        if self.control_db in {self.analysis_db, self.manifest_path}:
            raise MissionServiceError(503, "Mission 控制库必须与合成分析库物理隔离")
        self.manifest = self._validate_synthetic_source()
        self.dataset_hash = str(self.manifest["dataset_content_sha256"])
        self.analysis_date = str(self.manifest["analysis_as_of_date"])
        self.mission_id = f"mission-{self.analysis_date.replace('-', '')}-{self.dataset_hash[7:15]}"
        self._initialize_control_store()

    @classmethod
    def from_environment(cls) -> "MissionService":
        if os.environ.get("FQ_MISSION_DEMO_ENABLED", "").strip() != "1":
            raise MissionServiceError(404, "Mission 公网演示未启用")

        required = {
            "FQ_SYNTHETIC_DB_PATH": os.environ.get("FQ_SYNTHETIC_DB_PATH"),
            "FQ_MISSION_CONTROL_DB": os.environ.get("FQ_MISSION_CONTROL_DB"),
            "FQ_MISSION_EXPORT_DIR": os.environ.get("FQ_MISSION_EXPORT_DIR"),
        }
        missing = [name for name, value in required.items() if not value or not value.strip()]
        if missing:
            raise MissionServiceError(
                503,
                "Mission 数据源未显式配置: " + ", ".join(missing),
            )
        analysis_db = Path(str(required["FQ_SYNTHETIC_DB_PATH"])).resolve()
        control_db = Path(str(required["FQ_MISSION_CONTROL_DB"])).resolve()
        export_dir = Path(str(required["FQ_MISSION_EXPORT_DIR"])).resolve()
        try:
            db_stat = analysis_db.stat()
            manifest_bytes = analysis_db.with_suffix(".manifest.json").read_bytes()
        except OSError:
            return cls(analysis_db, control_db, export_dir)
        return _cached_service(
            str(analysis_db),
            str(control_db),
            str(export_dir),
            db_stat.st_size,
            db_stat.st_mtime_ns,
            hashlib.sha256(manifest_bytes).hexdigest(),
        )

    def _validate_synthetic_source(self) -> dict[str, Any]:
        if not self.analysis_db.is_file() or not self.manifest_path.is_file():
            raise MissionServiceError(503, "合成 DuckDB 或相邻 manifest 不存在")
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MissionServiceError(503, "合成数据 manifest 无法读取") from exc

        if manifest.get("data_profile") != "synthetic" or manifest.get("contains_real_data") is not False:
            raise MissionServiceError(503, "Mission 只允许 contains_real_data=false 的 synthetic 数据")
        if manifest.get("database_filename") != self.analysis_db.name:
            raise MissionServiceError(503, "manifest 与 DuckDB 文件名不匹配")
        if manifest.get("source") != "generated_from_code_only":
            raise MissionServiceError(503, "Mission 数据不是由合成生成器独立产生")
        if not SHA256_PATTERN.fullmatch(str(manifest.get("dataset_content_sha256", ""))):
            raise MissionServiceError(503, "manifest dataset_content_sha256 无效")

        claimed_manifest_hash = manifest.get("manifest_sha256")
        unsigned = dict(manifest)
        unsigned.pop("manifest_sha256", None)
        if claimed_manifest_hash != _canonical_hash(unsigned):
            raise MissionServiceError(503, "manifest 完整性校验失败")

        try:
            validation = validate_synthetic_database(self.analysis_db)
            conn = duckdb.connect(str(self.analysis_db), read_only=True)
            try:
                content_sha256 = compute_dataset_content_sha256(conn)
            finally:
                conn.close()
        except (duckdb.Error, OSError, ValueError) as exc:
            raise MissionServiceError(503, "合成 DuckDB 隐私或结构校验失败") from exc
        if content_sha256 != manifest["dataset_content_sha256"]:
            raise MissionServiceError(503, "合成 DuckDB 内容哈希与 manifest 不一致")
        expected_counts = manifest.get("validation", {}).get("row_counts")
        if validation["row_counts"] != expected_counts:
            raise MissionServiceError(503, "合成 DuckDB 行数与 manifest 不一致")
        return manifest

    def _initialize_control_store(self) -> None:
        self.control_db.parent.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.control_db.parent, self.export_dir):
            try:
                os.chmod(path, 0o700)
            except OSError:
                pass
        with sqlite3.connect(self.control_db) as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS mission_state (
                    mission_id TEXT PRIMARY KEY,
                    dataset_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    approved_by TEXT,
                    approved_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency_records (
                    idempotency_key TEXT PRIMARY KEY,
                    mission_id TEXT,
                    operation TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mission_exports (
                    export_id TEXT PRIMARY KEY,
                    mission_id TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    experiment_count INTEGER NOT NULL DEFAULT 0,
                    holdout_count INTEGER NOT NULL DEFAULT 0,
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            export_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(mission_exports)")
            }
            if "experiment_count" not in export_columns:
                conn.execute(
                    "ALTER TABLE mission_exports ADD COLUMN experiment_count INTEGER NOT NULL DEFAULT 0"
                )
            if "holdout_count" not in export_columns:
                conn.execute(
                    "ALTER TABLE mission_exports ADD COLUMN holdout_count INTEGER NOT NULL DEFAULT 0"
                )
            idempotency_columns = {
                str(row[1]) for row in conn.execute("PRAGMA table_info(idempotency_records)")
            }
            if "mission_id" not in idempotency_columns:
                conn.execute("ALTER TABLE idempotency_records ADD COLUMN mission_id TEXT")
            legacy_records = conn.execute(
                "SELECT idempotency_key, response_json FROM idempotency_records WHERE mission_id IS NULL"
            ).fetchall()
            for key, response_json in legacy_records:
                try:
                    legacy_mission_id = json.loads(str(response_json)).get("mission_id")
                except (json.JSONDecodeError, TypeError, AttributeError):
                    legacy_mission_id = None
                if legacy_mission_id:
                    conn.execute(
                        "UPDATE idempotency_records SET mission_id=? WHERE idempotency_key=?",
                        (str(legacy_mission_id), str(key)),
                    )
            conn.execute(
                """
                INSERT OR IGNORE INTO mission_state
                    (mission_id, dataset_hash, status, version, updated_at)
                VALUES (?, ?, 'AWAITING_APPROVAL', 1, ?)
                """,
                (self.mission_id, self.dataset_hash, _utc_now()),
            )
        try:
            os.chmod(self.control_db, 0o600)
        except OSError:
            pass

    def _connect_analysis(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.analysis_db), read_only=True)

    def _provenance(self) -> dict[str, Any]:
        return {
            "data_profile": "synthetic",
            "contains_real_data": False,
            "dataset_version": self.manifest["dataset_version"],
            "dataset_content_sha256": self.dataset_hash,
            "analysis_as_of_date": self.analysis_date,
            "metric_versions": [
                "customer-origin-v1",
                "customer-lifecycle-v1",
                "channel-customer-quality-v1",
            ],
        }

    @staticmethod
    def _demo_reset_enabled() -> bool:
        return os.environ.get("FQ_MISSION_DEMO_RESET_ENABLED", "").strip() == "1"

    def _read_state(self, mission_id: str) -> sqlite3.Row:
        if mission_id != self.mission_id:
            raise MissionServiceError(404, "Mission 不存在")
        with sqlite3.connect(self.control_db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM mission_state WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
        if row is None:
            raise MissionServiceError(404, "Mission 不存在")
        return row

    def _channel_metrics(self) -> list[dict[str, Any]]:
        conn = self._connect_analysis()
        try:
            rows = conn.execute(
                """
                SELECT
                    first_paid_channel,
                    cohort_customers,
                    mature_30d_customers,
                    second_paid_rate_30d,
                    median_days_to_second_paid,
                    cross_channel_rate,
                    avg_net_value_180d
                FROM sem_channel_customer_quality
                ORDER BY cohort_customers DESC
                """
            ).fetchall()
        finally:
            conn.close()
        return [
            {
                "channel": row[0],
                "first_paid_customers": int(row[1]),
                "mature_30d_customers": int(row[2]),
                "second_paid_rate_30d": float(row[3]),
                "median_days_to_second_paid": float(row[4]) if row[4] is not None else None,
                "cross_channel_rate": float(row[5]),
                "avg_net_value_180d": float(row[6]),
            }
            for row in rows
        ]

    def _target_audience(self, target_channel: str) -> dict[str, Any]:
        conn = self._connect_analysis()
        try:
            row = conn.execute(
                """
                WITH ranked_paid AS (
                    SELECT
                        orders.synthetic_user_id,
                        orders.product_code,
                        row_number() OVER (
                            PARTITION BY orders.synthetic_user_id
                            ORDER BY orders.pay_time, orders.synthetic_order_id
                        ) AS sequence
                    FROM synthetic_orders orders
                    WHERE orders.order_status = 'PAID'
                ), eligible AS (
                    SELECT lifecycle.synthetic_user_id
                    FROM sem_customer_lifecycle_snapshot lifecycle
                    JOIN sem_customer_origin origin USING (synthetic_user_id)
                    WHERE lifecycle.lifecycle_stage = 'REPLENISHMENT_DUE'
                      AND origin.first_paid_channel = ?
                )
                SELECT product_code, COUNT(*) AS repeat_customers
                FROM ranked_paid
                JOIN eligible USING (synthetic_user_id)
                WHERE sequence = 2
                GROUP BY product_code
                ORDER BY repeat_customers DESC, product_code
                LIMIT 1
                """,
                [target_channel],
            ).fetchone()
            audience_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM sem_customer_lifecycle_snapshot lifecycle
                    JOIN sem_customer_origin origin USING (synthetic_user_id)
                    WHERE lifecycle.lifecycle_stage = 'REPLENISHMENT_DUE'
                      AND origin.first_paid_channel = ?
                    """,
                    [target_channel],
                ).fetchone()[0]
            )
            product_code = str(row[0]) if row else "SYN-P-003"
            product = conn.execute(
                """
                SELECT generic_product_name, list_price, synthetic_unit_cost, replenishment_cycle_days
                FROM synthetic_products WHERE product_code = ?
                """,
                [product_code],
            ).fetchone()
        finally:
            conn.close()
        return {
            "segment_key": f"{target_channel}:REPLENISHMENT_DUE",
            "segment_name": f"{target_channel}首购·待补货人群",
            "channel": target_channel,
            "lifecycle_stage": "REPLENISHMENT_DUE",
            "eligible_customers": audience_count,
            "activation_product": {
                "product_code": product_code,
                "product_name": str(product[0]),
                "list_price": float(product[1]),
                "synthetic_unit_cost": float(product[2]),
                "replenishment_cycle_days": int(product[3]),
            },
        }

    def _latest_export(self, mission_id: str, mission_version: int) -> dict[str, Any] | None:
        with sqlite3.connect(self.control_db) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT export_id, sha256, row_count, experiment_count, holdout_count
                FROM mission_exports
                WHERE mission_id = ?
                ORDER BY created_at DESC, export_id DESC
                LIMIT 1
                """,
                (mission_id,),
            ).fetchone()
        if row is None:
            return None
        export_id = str(row["export_id"])
        return {
            "mission_id": mission_id,
            "mission_status": "WAITING_MEASUREMENT",
            "mission_version": mission_version,
            "export_id": export_id,
            "export_status": "DRAFT_EXPORT_READY",
            "row_count": int(row["row_count"]),
            "experiment_count": int(row["experiment_count"]),
            "holdout_count": int(row["holdout_count"]),
            "sha256": str(row["sha256"]),
            "download_url": (
                f"/api/v1/missions/{mission_id}/audience-exports/{export_id}/download"
            ),
            "expires_at": None,
            "data_provenance": self._provenance(),
        }

    def _build_snapshot(self, state: sqlite3.Row) -> dict[str, Any]:
        metrics = self._channel_metrics()
        volume_leader = max(metrics, key=lambda item: item["first_paid_customers"])
        quality_leader = max(
            metrics,
            key=lambda item: (item["second_paid_rate_30d"], item["avg_net_value_180d"]),
        )
        target = self._target_audience(str(volume_leader["channel"]))
        rate_gap = max(
            0.0,
            float(quality_leader["second_paid_rate_30d"])
            - float(volume_leader["second_paid_rate_30d"]),
        )
        assumed_uplift = round(max(0.02, rate_gap * 0.5), 4)
        experiment_count = int(target["eligible_customers"] * 0.9)
        unit_margin = (
            float(target["activation_product"]["list_price"])
            - float(target["activation_product"]["synthetic_unit_cost"])
        )
        expected_incremental_customers = round(experiment_count * assumed_uplift, 1)
        expected_incremental_margin = round(expected_incremental_customers * unit_margin, 2)

        approval = None
        if state["approved_by"]:
            approval = {
                "approved_by": state["approved_by"],
                "approved_at": state["approved_at"],
            }
        return {
            "mission_id": self.mission_id,
            "status": state["status"],
            "version": int(state["version"]),
            "title": "把直播大盘变成可复购资产",
            "executive_summary": (
                f"{volume_leader['channel']}带来最多首付费客户，但"
                f"{quality_leader['channel']} 30 天二单率高出 {rate_gap * 100:.1f} 个百分点。"
                "问题不是继续买流量，而是把流量变成客户资产。"
            ),
            "recommendation": (
                f"对 {target['eligible_customers']} 位{target['segment_name']}发起 90/10 对照实验，"
                f"以{target['activation_product']['product_name']}作为补货主张；"
                "实验组提升且增量毛利为正后，再扩大自动营销。"
            ),
            "decision": {
                "decision_type": "SECOND_PURCHASE_ACTIVATION",
                "volume_leader": volume_leader["channel"],
                "quality_leader": quality_leader["channel"],
                "guardrail": "未经审批不产生名单；必须保留 10% holdout",
                "next_action": "APPROVE_DRAFT_EXPORT" if state["status"] == "AWAITING_APPROVAL" else state["status"],
            },
            "channel_metrics": metrics,
            "target_audience": target,
            "economics": {
                "experiment_share": 0.9,
                "holdout_share": 0.1,
                "assumed_conversion_uplift": assumed_uplift,
                "expected_incremental_customers": expected_incremental_customers,
                "expected_incremental_margin": expected_incremental_margin,
                "currency": "CNY_SYNTHETIC",
                "assumption_note": "比较货架与直播的 30 天二单率差，仅取 50% 作为演示提升假设。",
            },
            "evidence": [
                {
                    "metric": "first_paid_customers",
                    "finding": f"{volume_leader['channel']}首付费客户 {volume_leader['first_paid_customers']} 人，规模第一",
                    "metric_version": "customer-origin-v1",
                },
                {
                    "metric": "second_paid_rate_30d",
                    "finding": (
                        f"{quality_leader['channel']} {quality_leader['second_paid_rate_30d'] * 100:.1f}%，"
                        f"{volume_leader['channel']} {volume_leader['second_paid_rate_30d'] * 100:.1f}%"
                    ),
                    "metric_version": "channel-customer-quality-v1",
                },
                {
                    "metric": "avg_net_value_180d",
                    "finding": (
                        f"{quality_leader['channel']} 180 天人均净价值 "
                        f"¥{quality_leader['avg_net_value_180d']:.0f}"
                    ),
                    "metric_version": "channel-customer-quality-v1",
                },
            ],
            "state_timeline": [
                {"state": item, "reached": MISSION_STATES.index(item) <= MISSION_STATES.index(state["status"])}
                for item in MISSION_STATES
            ],
            "approval": approval,
            "latest_export": (
                self._latest_export(self.mission_id, int(state["version"]))
                if state["status"] == "WAITING_MEASUREMENT"
                else None
            ),
            "demo_controls": {"reset_enabled": self._demo_reset_enabled()},
            "data_provenance": self._provenance(),
        }

    def get_today(self) -> dict[str, Any]:
        return self._build_snapshot(self._read_state(self.mission_id))

    def get_mission(self, mission_id: str) -> dict[str, Any]:
        return self._build_snapshot(self._read_state(mission_id))

    def diagnose(self, question: str) -> dict[str, Any]:
        normalized = question.strip()
        metrics = self._channel_metrics()
        volume = max(metrics, key=lambda item: item["first_paid_customers"])
        quality = max(metrics, key=lambda item: item["second_paid_rate_30d"])
        evidence: list[dict[str, Any]]
        if any(token in normalized for token in ("生命周期", "沉睡", "流失", "补货")):
            intent = "LIFECYCLE_DISTRIBUTION"
            conn = self._connect_analysis()
            try:
                rows = conn.execute(
                    """
                    SELECT lifecycle_stage, COUNT(*)
                    FROM sem_customer_lifecycle_snapshot
                    GROUP BY lifecycle_stage ORDER BY COUNT(*) DESC
                    """
                ).fetchall()
            finally:
                conn.close()
            evidence = [{"lifecycle_stage": row[0], "customers": int(row[1])} for row in rows]
            due = next((item["customers"] for item in evidence if item["lifecycle_stage"] == "REPLENISHMENT_DUE"), 0)
            answer = f"当前有 {due} 位客户处于待补货窗口，适合优先做可测量的二单激活。"
        elif any(token in normalized for token in ("产品", "新客", "老客", "商品")):
            intent = "PRODUCT_ROLE"
            conn = self._connect_analysis()
            try:
                rows = conn.execute(
                    """
                    WITH ranked AS (
                        SELECT product_code,
                               row_number() OVER (
                                   PARTITION BY synthetic_user_id
                                   ORDER BY pay_time, synthetic_order_id
                               ) AS sequence
                        FROM synthetic_orders WHERE order_status = 'PAID'
                    )
                    SELECT products.product_code, products.generic_product_name,
                           COUNT(*) FILTER (WHERE ranked.sequence = 1) AS first_order_customers,
                           COUNT(*) FILTER (WHERE ranked.sequence > 1) AS repeat_orders
                    FROM ranked JOIN synthetic_products products USING (product_code)
                    GROUP BY products.product_code, products.generic_product_name
                    ORDER BY repeat_orders DESC, first_order_customers DESC LIMIT 3
                    """
                ).fetchall()
            finally:
                conn.close()
            evidence = [
                {
                    "product_code": row[0],
                    "product_name": row[1],
                    "first_order_customers": int(row[2]),
                    "repeat_orders": int(row[3]),
                }
                for row in rows
            ]
            top = evidence[0]
            answer = f"{top['product_name']}的复购订单数最高，更适合作为老客激活主张，而不是只看首单销量。"
        else:
            intent = "CHANNEL_QUALITY"
            evidence = metrics
            gap = (quality["second_paid_rate_30d"] - volume["second_paid_rate_30d"]) * 100
            answer = (
                f"{volume['channel']}是规模入口，但{quality['channel']}是质量标杆："
                f"30 天二单率高 {gap:.1f} 个百分点。"
                "CEO 应把直播人群的复购转化作为当前 Mission。"
            )
        return {
            "question": normalized,
            "intent": intent,
            "answer_mode": "DETERMINISTIC_TOOL",
            "answer": answer,
            "evidence": evidence,
            "limitations": [
                "当前仅支持渠道质量、生命周期和产品角色三类受控问题",
                "数值为公网演示合成数据，不是生产经营结论",
            ],
            "data_provenance": self._provenance(),
        }

    def approve(
        self,
        mission_id: str,
        actor: str,
        if_match: str,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if mission_id != self.mission_id:
            raise MissionServiceError(404, "Mission 不存在")
        expected_version = _parse_version(if_match)
        request_hash = _canonical_hash(
            {"mission_id": mission_id, "actor": actor, "payload": payload}
        )
        now = _utc_now()
        conn = sqlite3.connect(self.control_db)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM idempotency_records WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["operation"] != "approve" or existing["request_hash"] != request_hash:
                    raise MissionServiceError(409, "Idempotency-Key 已被其他请求使用")
                conn.rollback()
                return json.loads(existing["response_json"])
            state = conn.execute(
                "SELECT * FROM mission_state WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
            if state is None:
                raise MissionServiceError(404, "Mission 不存在")
            if int(state["version"]) != expected_version:
                raise MissionServiceError(409, f"Mission 版本已变更，当前为 {state['version']}")
            if state["status"] != "AWAITING_APPROVAL":
                raise MissionServiceError(409, f"当前状态 {state['status']} 不允许审批")
            conn.execute(
                """
                UPDATE mission_state
                SET status='APPROVED', version=version+1,
                    approved_by=?, approved_at=?, updated_at=?
                WHERE mission_id=?
                """,
                (actor, now, now, mission_id),
            )
            updated = conn.execute(
                "SELECT * FROM mission_state WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
            response = self._build_snapshot(updated)
            conn.execute(
                """
                INSERT INTO idempotency_records
                    (idempotency_key, mission_id, operation, request_hash, response_json, created_at)
                VALUES (?, ?, 'approve', ?, ?, ?)
                """,
                (idempotency_key, mission_id, request_hash, json.dumps(response, ensure_ascii=False), now),
            )
            conn.commit()
            return response
        except MissionServiceError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _eligible_user_ids(self, target_channel: str) -> list[str]:
        conn = self._connect_analysis()
        try:
            return [
                str(row[0])
                for row in conn.execute(
                    """
                    SELECT lifecycle.synthetic_user_id
                    FROM sem_customer_lifecycle_snapshot lifecycle
                    JOIN sem_customer_origin origin USING (synthetic_user_id)
                    WHERE lifecycle.lifecycle_stage = 'REPLENISHMENT_DUE'
                      AND origin.first_paid_channel = ?
                    ORDER BY lifecycle.synthetic_user_id
                    """,
                    [target_channel],
                ).fetchall()
            ]
        finally:
            conn.close()

    def create_draft_export(
        self,
        mission_id: str,
        actor: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        if mission_id != self.mission_id:
            raise MissionServiceError(404, "Mission 不存在")
        expected_version = _parse_version(if_match)
        request_hash = _canonical_hash({"mission_id": mission_id, "actor": actor})
        now = _utc_now()
        conn = sqlite3.connect(self.control_db)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM idempotency_records WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["operation"] != "draft_export" or existing["request_hash"] != request_hash:
                    raise MissionServiceError(409, "Idempotency-Key 已被其他请求使用")
                conn.rollback()
                return json.loads(existing["response_json"])
            state = conn.execute(
                "SELECT * FROM mission_state WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
            if state is None:
                raise MissionServiceError(404, "Mission 不存在")
            if int(state["version"]) != expected_version:
                raise MissionServiceError(409, f"Mission 版本已变更，当前为 {state['version']}")
            if state["status"] != "APPROVED":
                raise MissionServiceError(409, "只有 APPROVED Mission 可生成草稿名单")

            snapshot = self._build_snapshot(state)
            target_channel = str(snapshot["target_audience"]["channel"])
            user_ids = self._eligible_user_ids(target_channel)
            export_id = f"draft-{self.dataset_hash[7:15]}-{expected_version}"
            final_path = self.export_dir / f"{export_id}.csv"
            fd, temp_name = tempfile.mkstemp(prefix=f".{export_id}-", suffix=".tmp", dir=self.export_dir)
            experiment_count = 0
            holdout_count = 0
            try:
                with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                    writer = csv.writer(handle)
                    writer.writerow(["synthetic_user_id", "mission_id", "experiment_arm"])
                    for user_id in user_ids:
                        bucket = int(hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:8], 16) % 10
                        arm = "HOLDOUT" if bucket == 0 else "EXPERIMENT"
                        holdout_count += arm == "HOLDOUT"
                        experiment_count += arm == "EXPERIMENT"
                        writer.writerow([user_id, mission_id, arm])
                    handle.flush()
                    os.fsync(handle.fileno())
                os.chmod(temp_name, 0o600)
                os.replace(temp_name, final_path)
            finally:
                if os.path.exists(temp_name):
                    os.unlink(temp_name)
            file_sha = f"sha256:{hashlib.sha256(final_path.read_bytes()).hexdigest()}"
            conn.execute(
                """
                INSERT INTO mission_exports
                    (export_id, mission_id, path, sha256, row_count,
                     experiment_count, holdout_count, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    export_id,
                    mission_id,
                    str(final_path),
                    file_sha,
                    len(user_ids),
                    experiment_count,
                    holdout_count,
                    actor,
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE mission_state
                SET status='WAITING_MEASUREMENT', version=version+1, updated_at=?
                WHERE mission_id=?
                """,
                (now, mission_id),
            )
            response = {
                "mission_id": mission_id,
                "mission_status": "WAITING_MEASUREMENT",
                "mission_version": expected_version + 1,
                "export_id": export_id,
                "export_status": "DRAFT_EXPORT_READY",
                "row_count": len(user_ids),
                "experiment_count": experiment_count,
                "holdout_count": holdout_count,
                "sha256": file_sha,
                "download_url": f"/api/v1/missions/{mission_id}/audience-exports/{export_id}/download",
                "expires_at": None,
                "data_provenance": self._provenance(),
            }
            conn.execute(
                """
                INSERT INTO idempotency_records
                    (idempotency_key, mission_id, operation, request_hash, response_json, created_at)
                VALUES (?, ?, 'draft_export', ?, ?, ?)
                """,
                (idempotency_key, mission_id, request_hash, json.dumps(response, ensure_ascii=False), now),
            )
            conn.commit()
            return response
        except MissionServiceError:
            conn.rollback()
            raise
        finally:
            conn.close()

    def reset_demo(
        self,
        mission_id: str,
        actor: str,
        if_match: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Restore the synthetic Mission to its judge-demo starting state.

        This path is independently gated from the Mission demo itself. Existing
        synthetic exports are moved into a private recovery archive instead of
        being deleted, and the read-only analysis DuckDB is never opened for write.
        """
        if not self._demo_reset_enabled():
            raise MissionServiceError(404, "Mission 演示重置未启用")
        if mission_id != self.mission_id:
            raise MissionServiceError(404, "Mission 不存在")

        expected_version = _parse_version(if_match)
        request_hash = _canonical_hash({"mission_id": mission_id, "actor": actor})
        now = _utc_now()
        moved_exports: list[tuple[Path, Path]] = []
        conn = sqlite3.connect(self.control_db)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM idempotency_records WHERE idempotency_key = ?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                if existing["operation"] != "demo_reset" or existing["request_hash"] != request_hash:
                    raise MissionServiceError(409, "Idempotency-Key 已被其他请求使用")
                conn.rollback()
                return json.loads(existing["response_json"])

            state = conn.execute(
                "SELECT * FROM mission_state WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
            if state is None:
                raise MissionServiceError(404, "Mission 不存在")
            if int(state["version"]) != expected_version:
                raise MissionServiceError(409, f"Mission 版本已变更，当前为 {state['version']}")

            export_rows = conn.execute(
                "SELECT path FROM mission_exports WHERE mission_id = ? ORDER BY export_id",
                (mission_id,),
            ).fetchall()
            export_paths: list[Path] = []
            for row in export_rows:
                export_path = Path(str(row["path"])).resolve()
                if export_path.parent != self.export_dir:
                    raise MissionServiceError(503, "DRAFT_EXPORT 路径越界，拒绝重置")
                if export_path.exists() and not export_path.is_file():
                    raise MissionServiceError(503, "DRAFT_EXPORT 不是普通文件，拒绝重置")
                if export_path.is_file():
                    export_paths.append(export_path)

            if state["status"] == "AWAITING_APPROVAL" and not export_rows:
                response = self._build_snapshot(state)
                conn.execute(
                    """
                    INSERT INTO idempotency_records
                        (idempotency_key, mission_id, operation, request_hash, response_json, created_at)
                    VALUES (?, ?, 'demo_reset', ?, ?, ?)
                    """,
                    (idempotency_key, mission_id, request_hash, json.dumps(response, ensure_ascii=False), now),
                )
                conn.commit()
                return response

            archive_dir = self.export_dir / ".reset-archive" / mission_id / f"v{expected_version}"
            archive_dir.mkdir(parents=True, exist_ok=True)
            try:
                os.chmod(self.export_dir / ".reset-archive", 0o700)
                os.chmod(archive_dir.parent, 0o700)
                os.chmod(archive_dir, 0o700)
            except OSError:
                pass
            for export_path in export_paths:
                archive_path = archive_dir / export_path.name
                if archive_path.exists():
                    raise MissionServiceError(409, "演示归档目标已存在，请核对后重试")
                os.replace(export_path, archive_path)
                moved_exports.append((export_path, archive_path))

            conn.execute("DELETE FROM mission_exports WHERE mission_id = ?", (mission_id,))
            conn.execute("DELETE FROM idempotency_records WHERE mission_id = ?", (mission_id,))
            conn.execute(
                """
                UPDATE mission_state
                SET status='AWAITING_APPROVAL', version=version+1,
                    approved_by=NULL, approved_at=NULL, updated_at=?
                WHERE mission_id=?
                """,
                (now, mission_id),
            )
            updated = conn.execute(
                "SELECT * FROM mission_state WHERE mission_id = ?",
                (mission_id,),
            ).fetchone()
            response = self._build_snapshot(updated)
            conn.execute(
                """
                INSERT INTO idempotency_records
                    (idempotency_key, mission_id, operation, request_hash, response_json, created_at)
                VALUES (?, ?, 'demo_reset', ?, ?, ?)
                """,
                (idempotency_key, mission_id, request_hash, json.dumps(response, ensure_ascii=False), now),
            )
            conn.commit()
            return response
        except (MissionServiceError, OSError, sqlite3.Error) as exc:
            conn.rollback()
            for original_path, archive_path in reversed(moved_exports):
                if archive_path.is_file() and not original_path.exists():
                    os.replace(archive_path, original_path)
            if isinstance(exc, MissionServiceError):
                raise
            raise MissionServiceError(503, "Mission 演示重置失败") from exc
        finally:
            conn.close()

    def resolve_export(self, mission_id: str, export_id: str) -> Path:
        if mission_id != self.mission_id:
            raise MissionServiceError(404, "Mission 不存在")
        with sqlite3.connect(self.control_db) as conn:
            row = conn.execute(
                "SELECT path FROM mission_exports WHERE mission_id=? AND export_id=?",
                (mission_id, export_id),
            ).fetchone()
        if row is None:
            raise MissionServiceError(404, "DRAFT_EXPORT 不存在")
        path = Path(str(row[0])).resolve()
        if path.parent != self.export_dir or not path.is_file():
            raise MissionServiceError(404, "DRAFT_EXPORT 文件不存在")
        return path


@lru_cache(maxsize=16)
def _cached_service(
    analysis_db: str,
    control_db: str,
    export_dir: str,
    _db_size: int,
    _db_mtime_ns: int,
    _manifest_digest: str,
) -> MissionService:
    """Reuse a validated read-only source until its file signature changes."""
    return MissionService(Path(analysis_db), Path(control_db), Path(export_dir))
