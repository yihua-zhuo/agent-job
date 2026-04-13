"""销售服务单元测试"""
import pytest
from src.services.sales_service import SalesService
from src.models.opportunity import Stage


@pytest.fixture
def sales_service():
    """创建销售服务实例"""
    return SalesService()


@pytest.fixture
def sample_pipeline(sales_service):
    """创建示例管道"""
    result = sales_service.create_pipeline(1, {
        "name": "测试管道",
        "created_by": 1,
    })
    return result.data["id"]


class TestSalesService:
    """测试销售服务"""

    def test_create_and_get_pipeline(self, sales_service):
        """测试创建和获取管道"""
        result = sales_service.create_pipeline(1, {
            "name": "主销售管道",
            "created_by": 1,
        })
        assert bool(result) is True
        pipeline = result.data
        assert pipeline["name"] == "主销售管道"
        assert "lead" in pipeline["stages"]

        retrieved = sales_service.get_pipeline(1, pipeline["id"])
        assert bool(retrieved) is True
        assert retrieved.data["id"] == pipeline["id"]

    def test_create_opportunity(self, sales_service, sample_pipeline):
        """测试创建商机"""
        result = sales_service.create_opportunity(1, {
            "name": "测试商机",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": 50000,
        })
        assert bool(result) is True
        assert result.data["name"] == "测试商机"
        assert result.data["stage"] == "lead"

    def test_get_opportunity(self, sales_service, sample_pipeline):
        """测试获取商机详情"""
        r1 = sales_service.create_opportunity(1, {
            "name": "商机A",
            "stage": Stage.QUALIFIED,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": 30000,
        })
        opp_id = r1.data["id"]

        result = sales_service.get_opportunity(1, opp_id)
        assert bool(result) is True
        assert result.data["name"] == "商机A"

    def test_update_opportunity(self, sales_service, sample_pipeline):
        """测试更新商机"""
        r1 = sales_service.create_opportunity(1, {
            "name": "旧名称",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": 10000,
        })
        opp_id = r1.data["id"]

        result = sales_service.update_opportunity(1, opp_id, {
            "name": "新名称",
        })
        assert bool(result) is True
        assert result.data["name"] == "新名称"

    def test_change_stage(self, sales_service, sample_pipeline):
        """测试改变商机阶段"""
        r1 = sales_service.create_opportunity(1, {
            "name": "商机阶段测试",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": 10000,
        })
        opp_id = r1.data["id"]

        result = sales_service.change_stage(1, opp_id, Stage.PROPOSAL)
        assert bool(result) is True
        assert result.data["stage"] == Stage.PROPOSAL

    def test_list_opportunities(self, sales_service, sample_pipeline):
        """测试商机列表"""
        for i in range(3):
            sales_service.create_opportunity(1, {
                "name": f"商机{i}",
                "stage": Stage.LEAD,
                "owner_id": 1,
                "customer_id": i + 1,
                "pipeline_id": sample_pipeline,
                "amount": 10000 * (i + 1),
            })

        result = sales_service.list_opportunities(1, page=1, page_size=10)
        assert bool(result) is True
        assert result.data.total == 3
        assert len(result.data.items) == 3

    def test_list_pipelines(self, sales_service):
        """测试管道列表"""
        sales_service.create_pipeline(1, {"name": "管道A", "created_by": 1})
        sales_service.create_pipeline(1, {"name": "管道B", "created_by": 1})

        result = sales_service.list_pipelines(1)
        assert bool(result) is True
        assert len(result.data["items"]) >= 2

    def test_get_pipeline_stats(self, sales_service, sample_pipeline):
        """测试管道统计"""
        sales_service.create_opportunity(1, {
            "name": "商机统计测试",
            "stage": Stage.LEAD,
            "owner_id": 1,
            "customer_id": 1,
            "pipeline_id": sample_pipeline,
            "amount": 50000,
        })

        result = sales_service.get_pipeline_stats(1, sample_pipeline)
        assert bool(result) is True
        assert result.data["total"] == 1

    def test_get_pipeline_funnel(self, sales_service, sample_pipeline):
        """测试管道漏斗"""
        result = sales_service.get_pipeline_funnel(1, sample_pipeline)
        assert bool(result) is True
        assert "stages" in result.data

    def test_get_forecast(self, sales_service):
        """测试销售预测"""
        result = sales_service.get_forecast(1)
        assert bool(result) is True
        assert "forecast" in result.data
