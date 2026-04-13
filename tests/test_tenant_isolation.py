"""租户隔离中间件层测试套件"""
import pytest
from unittest.mock import MagicMock, patch
from flask import Flask, g


class TestTenantContext:
    """测试租户上下文设置"""

    def test_tenant_context_is_set(self):
        """验证中间件正确设置租户上下文"""
        # 模拟 Flask 请求上下文
        app = Flask(__name__)
        
        with app.test_request_context(headers={"Authorization": "Bearer test_token"}):
            with patch('src.internal.middleware.auth.decode_token') as mock_decode:
                # 模拟 JWT 解码返回租户信息
                mock_decode.return_value = {
                    "user_id": 1,
                    "tenant_id": 42,
                    "roles": ["admin"]
                }
                
                from src.internal.middleware.auth import require_auth, get_current_tenant_id
                
                @require_auth
                def protected_endpoint():
                    tenant_id = get_current_tenant_id()
                    assert tenant_id == 42, "租户ID应该从JWT中正确提取"
                    return {"success": True}
                
                result = protected_endpoint()
                assert result["success"] is True

    def test_tenant_context_none_without_auth(self):
        """验证未认证时租户上下文为空"""
        from src.internal.middleware.auth import get_current_tenant_id
        
        with patch('src.internal.middleware.auth.extract_token_from_header', return_value=None):
            tenant_id = get_current_tenant_id()
            assert tenant_id is None, "未认证时租户ID应该为None"


class TestCrossTenantAccess:
    """测试跨租户访问控制"""

    def test_cross_tenant_access_denied(self):
        """验证跨租户访问被拒绝"""
        from src.internal.middleware.tenant import require_tenant
        from src.internal.middleware.auth import get_current_tenant_id
        
        app = Flask(__name__)
        
        with app.test_request_context():
            # 模拟租户A上下文
            g.tenant_id = 1
            
            @require_tenant
            def access_tenant_data():
                # 模拟尝试访问租户B的数据
                current_tenant = get_current_tenant_id()
                requested_tenant = 2  # 租户B
                
                # 核心检查：当前租户与请求租户不匹配时应拒绝
                if current_tenant != requested_tenant:
                    return {"access": False, "reason": "跨租户访问被拒绝"}
                return {"access": True}
            
            result = access_tenant_data()
            assert result["access"] is False, "跨租户访问应该被拒绝"

    def test_same_tenant_access_allowed(self):
        """验证同租户访问被允许"""
        from src.internal.middleware.tenant import require_tenant
        from src.internal.middleware.auth import get_current_tenant_id
        
        app = Flask(__name__)
        
        with app.test_request_context():
            # 模拟租户A上下文
            g.tenant_id = 1
            
            @require_tenant
            def access_own_tenant():
                current_tenant = get_current_tenant_id()
                requested_tenant = 1  # 同一租户
                
                if current_tenant != requested_tenant:
                    return {"access": False}
                return {"access": True}
            
            result = access_own_tenant()
            assert result["access"] is True, "同租户访问应该被允许"


class TestTenantIdRequired:
    """测试 tenant_id 必需性"""

    def test_tenant_id_required_for_protected_routes(self):
        """验证受保护路由需要 tenant_id"""
        from src.internal.middleware.tenant import require_tenant
        from src.internal.pkg.errors import AppError
        
        @require_tenant
        def protected_route():
            return {"data": "secret"}
        
        # 无 tenant_id 上下文
        app = Flask(__name__)
        with app.test_request_context():
            with pytest.raises(AppError) as exc_info:
                protected_route()
            
            assert "缺少租户信息" in str(exc_info.value.message) or exc_info.value.code == 3001

    def test_missing_tenant_id_returns_401(self):
        """验证缺少 tenant_id 时返回 401"""
        from src.internal.middleware.tenant import require_tenant
        from src.internal.pkg.errors import AppError, ErrorCode
        
        @require_tenant
        def protected_route():
            return {"data": "secret"}
        
        app = Flask(__name__)
        with app.test_request_context():
            try:
                protected_route()
                assert False, "应该抛出异常"
            except AppError as e:
                assert e.status_code == 401, "缺少租户信息应返回401"
                assert e.code == ErrorCode.UNAUTHORIZED


class TestRepositoryFilters:
    """测试 Repository 层租户过滤"""

    def test_repository_filters_by_tenant(self):
        """验证 repository 层按租户过滤数据"""
        # 检查 repository 是否存在并有租户过滤逻辑
        import os
        repo_path = "/home/node/.openclaw/workspace/dev-agent-system/src/internal/repository"
        
        # repository 目录应该是空的（未实现）
        repo_files = os.listdir(repo_path) if os.path.exists(repo_path) else []
        non_init_files = [f for f in repo_files if f != "__init__.py" and f != "__pycache__"]
        
        if non_init_files:
            # 如果有 repository 文件，检查是否有租户过滤
            for filename in non_init_files:
                if filename.endswith(".py"):
                    filepath = os.path.join(repo_path, filename)
                    with open(filepath) as f:
                        content = f.read()
                        # 检查是否有 tenant_id 过滤逻辑
                        has_filter = "tenant_id" in content and ("filter" in content or "WHERE" in content)
                        assert has_filter, f"{filename} 应包含 tenant_id 过滤逻辑"
        else:
            # Repository 未实现，这是个问题
            pytest.fail("Repository 层未实现，缺少租户数据过滤机制")

    def test_model_has_tenant_id_field(self):
        """验证模型包含 tenant_id 字段"""
        from src.models.customer import Customer
        import inspect
        
        # 获取 Customer 的字段
        fields = [f for f in dir(Customer) if not f.startswith("_")]
        init_signature = inspect.signature(Customer.__init__)
        param_names = list(init_signature.parameters.keys())
        
        assert "tenant_id" in param_names, \
            f"Customer 模型缺少 tenant_id 字段，当前字段: {param_names}"


class TestMiddlewareIntegration:
    """测试中间件集成"""

    def test_tenant_isolation_middleware_registered(self):
        """验证 app.py 中注册了租户隔离中间件"""
        with open("/home/node/.openclaw/workspace/dev-agent-system/src/app.py") as f:
            content = f.read()
        
        # 检查是否注册了租户中间件
        has_tenant_middleware = (
            "tenant_isolation_middleware" in content or
            "TenantMiddleware" in content or
            "require_tenant" in content
        )
        
        assert has_tenant_middleware, \
            "app.py 未注册租户隔离中间件"

    def test_auth_middleware_sets_tenant_context(self):
        """验证 auth 中间件正确设置 tenant_id 到 g"""
        from src.internal.middleware.auth import require_auth
        from flask import g
        
        app = Flask(__name__)
        
        with app.test_request_context(headers={"Authorization": "Bearer valid_token"}):
            with patch('src.internal.middleware.auth.decode_token') as mock_decode:
                mock_decode.return_value = {
                    "user_id": 1,
                    "tenant_id": 99,
                    "roles": []
                }
                
                @require_auth
                def test_endpoint():
                    assert hasattr(g, "tenant_id"), "g 应有 tenant_id 属性"
                    assert g.tenant_id == 99, "tenant_id 应从 JWT 中提取"
                    return {"ok": True}
                
                result = test_endpoint()
                assert result["ok"] is True


class TestEndToEnd:
    """端到端测试"""

    def test_request_without_tenant_id_rejected(self):
        """验证不带 tenant_id 的请求被拒绝"""
        from src.internal.middleware.auth import require_auth
        from src.internal.middleware.tenant import require_tenant
        from src.internal.pkg.errors import AppError
        
        @require_auth
        @require_tenant
        def protected_endpoint():
            return {"data": "success"}
        
        app = Flask(__name__)
        
        # 模拟带有效 token 但无 tenant_id 的请求
        with app.test_request_context(headers={"Authorization": "Bearer valid_token"}):
            with patch('src.internal.middleware.auth.decode_token') as mock_decode:
                mock_decode.return_value = {
                    "user_id": 1,
                    # 无 tenant_id
                    "roles": []
                }
                
                try:
                    protected_endpoint()
                    assert False, "应该抛出异常"
                except AppError as e:
                    assert e.status_code == 401

    def test_tenant_a_cannot_access_tenant_b_data(self):
        """验证租户A无法访问租户B的数据 - 核心隔离测试"""
        from src.internal.middleware.auth import get_current_tenant_id
        from src.internal.middleware.tenant import require_tenant
        
        app = Flask(__name__)
        
        with app.test_request_context():
            # 模拟租户A用户
            g.tenant_id = 10
            g.user_id = 100
            
            @require_tenant
            def get_customer_data(customer_id):
                """模拟获取客户数据"""
                current_tenant = get_current_tenant_id()
                
                # 模拟：从数据库查询时检查租户匹配
                # 假设 customer 属于租户 20 (租户B)
                customer_tenant = 20
                
                if current_tenant != customer_tenant:
                    # 这是核心隔离检查点
                    raise AppError(
                        ErrorCode.FORBIDDEN,
                        "无权访问此客户数据",
                        403
                    )
                return {"customer_id": customer_id}
            
            with pytest.raises(AppError) as exc_info:
                get_customer_data(customer_id=1)
            
            assert exc_info.value.status_code == 403
            assert "无权访问" in str(exc_info.value.message)
