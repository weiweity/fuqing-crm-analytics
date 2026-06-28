"""Sprint 143 改名 ROI → 正装转化分析 回归测试."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class TestROIRenameSprint143:
    """Q10 拍板: 仅前端文案改名，API 保留."""

    def test_frontend_copy_renamed(self):
        """SamplingView、Sidebar 和 route name 使用正装转化文案."""
        sampling_view = (REPO_ROOT / "frontend-vue3/src/views/SamplingView.vue").read_text()
        sidebar = (REPO_ROOT / "frontend-vue3/src/components/Sidebar.vue").read_text()
        router = (REPO_ROOT / "frontend-vue3/src/router/index.ts").read_text()

        assert "U先/百补派样正装转化分析" in sampling_view
        assert "派样正装转化分析" in sampling_view
        assert "U先/百补派样ROI" not in sampling_view
        assert "派样正装转化" in sidebar
        assert "派样看板', key: '/sampling'" not in sidebar
        assert "name: 'SamplingConversion'" in router

    def test_backend_sampling_roi_api_unchanged(self):
        """后端 /v1/sampling/roi 保留，避免 breaking change."""
        sampling_router = (REPO_ROOT / "backend/routers/sampling.py").read_text()
        sampling_api = (REPO_ROOT / "frontend-vue3/src/api/sampling.ts").read_text()

        assert '@router.get("/roi"' in sampling_router
        assert "fetchSamplingROI" in sampling_api
        assert "client.get('/v1/sampling/roi'" in sampling_api
