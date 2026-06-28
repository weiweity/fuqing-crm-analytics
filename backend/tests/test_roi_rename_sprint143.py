"""Sprint 143 改名 ROI → 正装转化分析 回归测试."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class TestROIRenameSprint143:
    """Q10 拍板: 仅前端文案改名，API 保留."""

    def test_frontend_copy_renamed(self):
        """SamplingView、Sidebar/NavBar 替代品 和 route name 使用正装转化文案.
        Sprint 158 删 Sidebar.vue 用 NavBar.vue + config/navigations.ts 替代.
        L3 精准: test 改读 navigations.ts 替代 Sidebar.vue, 验证渠道名在 nav config 出现.
        """
        sampling_view = (REPO_ROOT / "frontend-vue3/src/views/SamplingView.vue").read_text()
        nav_config = (REPO_ROOT / "frontend-vue3/src/config/navigations.ts").read_text()
        router = (REPO_ROOT / "frontend-vue3/src/router/index.ts").read_text()

        assert "U先/百补派样正装转化分析" in sampling_view
        assert "派样正装转化分析" in sampling_view
        assert "U先/百补派样ROI" not in sampling_view
        # Sprint 158: 派样正装转化文案在 nav config (替代 Sidebar)
        assert "派样正装转化" in nav_config
        # 验证 nav config 不再用老名字
        assert "派样看板" not in nav_config
        assert "name: 'SamplingConversion'" in router

    def test_backend_sampling_roi_api_unchanged(self):
        """后端 /v1/sampling/roi 保留，避免 breaking change."""
        sampling_router = (REPO_ROOT / "backend/routers/sampling.py").read_text()
        sampling_api = (REPO_ROOT / "frontend-vue3/src/api/sampling.ts").read_text()

        assert '@router.get("/roi"' in sampling_router
        assert "fetchSamplingROI" in sampling_api
        assert "client.get('/v1/sampling/roi'" in sampling_api
