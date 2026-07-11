"""Sprint 205: 派样渠道同比字段必须穿透 FastAPI response_model 契约。"""

from backend.contracts.sampling import SamplingROIResponse


def test_sampling_roi_response_preserves_new_channel_compare_metrics():
    """服务层写入的新 YOY/MOM 指标不能被 Pydantic 响应契约静默过滤。"""
    response = SamplingROIResponse.model_validate(
        {
            "summary": {
                "channels": [
                    {
                        "channel": "TTL派样",
                        "sample_users": 3443,
                        "sample_users_yoy_pct": -0.7798,
                        "sample_users_mom_pct": 0.1234,
                        "nonfull_repurchase_users_yoy_pct": -0.555,
                        "nonfull_repurchase_users_mom_pct": 0.08,
                    }
                ]
            },
            "category_breakdown": [],
            "time_range": {
                "start": "2026-07-01",
                "end": "2026-07-11",
                "window_days": 30,
            },
        }
    )

    channel = response.model_dump()["summary"]["channels"][0]
    assert channel["sample_users_yoy_pct"] == -0.7798
    assert channel["sample_users_mom_pct"] == 0.1234
    assert channel["nonfull_repurchase_users_yoy_pct"] == -0.555
    assert channel["nonfull_repurchase_users_mom_pct"] == 0.08
