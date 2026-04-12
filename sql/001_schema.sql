-- =============================================================================
-- CRM 生产级数据库架构
-- 版本: 1.0.0
-- 创建时间: 2026-04-12
-- 描述: 完整的 51 张表多租户 CRM 数据库设计
-- =============================================================================

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================================
-- 1. 租户与组织（8张表）
-- =============================================================================

-- ----------------------------
-- 1.1 租户表
-- ----------------------------
CREATE TABLE tenants (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '租户ID',
    name VARCHAR(128) NOT NULL COMMENT '租户名称',
    code VARCHAR(64) NOT NULL UNIQUE COMMENT '租户编码',
    domain VARCHAR(255) NULL COMMENT '域名',
    logo VARCHAR(512) NULL COMMENT 'Logo URL',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=正常, 2=试用',
    plan_type VARCHAR(32) NULL COMMENT '套餐类型: free/pro/enterprise',
    max_users INT NULL COMMENT '最大用户数',
    max_customers BIGINT NULL COMMENT '最大客户数',
    expire_at DATETIME NULL COMMENT '过期时间',
    settings JSON NULL COMMENT '租户配置',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_tenants_code (code),
    INDEX idx_tenants_status (status),
    INDEX idx_tenants_expire_at (expire_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户表';

-- ----------------------------
-- 1.2 组织表
-- ----------------------------
CREATE TABLE organizations (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '组织ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(128) NOT NULL COMMENT '组织名称',
    code VARCHAR(64) NULL COMMENT '组织编码',
    type VARCHAR(32) NULL COMMENT '组织类型: company/division/department',
    parent_id BIGINT NULL COMMENT '上级组织ID',
    level INT NOT NULL DEFAULT 1 COMMENT '层级深度',
    path VARCHAR(512) NULL COMMENT '路径编码: /1/2/3/',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=正常',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    settings JSON NULL COMMENT '组织配置',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_org_tenant_id (tenant_id),
    INDEX idx_org_parent_id (parent_id),
    INDEX idx_org_path (path),
    INDEX idx_org_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='组织表';

-- ----------------------------
-- 1.3 部门表
-- ----------------------------
CREATE TABLE departments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '部门ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    org_id BIGINT NOT NULL COMMENT '组织ID',
    name VARCHAR(128) NOT NULL COMMENT '部门名称',
    code VARCHAR(64) NULL COMMENT '部门编码',
    parent_id BIGINT NULL COMMENT '上级部门ID',
    leader_id BIGINT NULL COMMENT '部门负责人ID',
    level INT NOT NULL DEFAULT 1 COMMENT '层级深度',
    path VARCHAR(512) NULL COMMENT '路径编码',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=正常',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_dept_tenant_id (tenant_id),
    INDEX idx_dept_org_id (org_id),
    INDEX idx_dept_parent_id (parent_id),
    INDEX idx_dept_leader_id (leader_id),
    INDEX idx_dept_path (path)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='部门表';

-- ----------------------------
-- 1.4 用户表
-- ----------------------------
CREATE TABLE users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    username VARCHAR(64) NOT NULL COMMENT '用户名',
    email VARCHAR(255) NOT NULL COMMENT '邮箱',
    phone VARCHAR(32) NULL COMMENT '手机号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    real_name VARCHAR(64) NULL COMMENT '真实姓名',
    nickname VARCHAR(64) NULL COMMENT '昵称',
    avatar VARCHAR(512) NULL COMMENT '头像URL',
    dept_id BIGINT NULL COMMENT '部门ID',
    position VARCHAR(128) NULL COMMENT '职位',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=正常, 2=待激活',
    user_type TINYINT NOT NULL DEFAULT 1 COMMENT '类型: 1=普通用户, 2=管理员, 3=超级管理员',
    last_login_at DATETIME NULL COMMENT '最后登录时间',
    last_login_ip VARCHAR(64) NULL COMMENT '最后登录IP',
    login_count INT NOT NULL DEFAULT 0 COMMENT '登录次数',
    settings JSON NULL COMMENT '用户配置',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_users_tenant_username (tenant_id, username),
    UNIQUE INDEX idx_users_tenant_email (tenant_id, email),
    INDEX idx_users_phone (phone),
    INDEX idx_users_dept_id (dept_id),
    INDEX idx_users_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ----------------------------
-- 1.5 角色表
-- ----------------------------
CREATE TABLE roles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '角色ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(64) NOT NULL COMMENT '角色名称',
    code VARCHAR(64) NOT NULL COMMENT '角色编码',
    description VARCHAR(255) NULL COMMENT '角色描述',
    role_type TINYINT NOT NULL DEFAULT 1 COMMENT '类型: 1=系统角色, 2=自定义角色',
    is_system TINYINT NOT NULL DEFAULT 0 COMMENT '是否系统内置: 0=否, 1=是',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=禁用, 1=正常',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_roles_tenant_code (tenant_id, code),
    INDEX idx_roles_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色表';

-- ----------------------------
-- 1.6 权限表
-- ----------------------------
CREATE TABLE permissions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '权限ID',
    tenant_id BIGINT NOT NULL DEFAULT 0 COMMENT '租户ID (0表示全局权限)',
    name VARCHAR(64) NOT NULL COMMENT '权限名称',
    code VARCHAR(128) NOT NULL COMMENT '权限编码',
    resource VARCHAR(64) NOT NULL COMMENT '资源类型: customers, leads, opportunities...',
    action VARCHAR(32) NOT NULL COMMENT '操作类型: create, read, update, delete...',
    description VARCHAR(255) NULL COMMENT '权限描述',
    parent_id BIGINT NULL COMMENT '上级权限ID',
    level INT NOT NULL DEFAULT 1 COMMENT '层级深度',
    path VARCHAR(512) NULL COMMENT '路径编码',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_permissions_code (code),
    INDEX idx_permissions_tenant_id (tenant_id),
    INDEX idx_permissions_resource_action (resource, action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='权限表';

-- ----------------------------
-- 1.7 角色权限关联表
-- ----------------------------
CREATE TABLE role_permissions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    permission_id BIGINT NOT NULL COMMENT '权限ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by BIGINT NULL COMMENT '创建人',
    UNIQUE INDEX idx_role_permissions_unique (role_id, permission_id),
    INDEX idx_role_permissions_role_id (role_id),
    INDEX idx_role_permissions_permission_id (permission_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='角色权限关联表';

-- ----------------------------
-- 1.8 用户角色关联表
-- ----------------------------
CREATE TABLE user_roles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    role_id BIGINT NOT NULL COMMENT '角色ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by BIGINT NULL COMMENT '创建人',
    UNIQUE INDEX idx_user_roles_unique (user_id, role_id),
    INDEX idx_user_roles_user_id (user_id),
    INDEX idx_user_roles_role_id (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户角色关联表';

-- =============================================================================
-- 2. 客户核心（10张表）
-- =============================================================================

-- ----------------------------
-- 2.1 客户表
-- ----------------------------
CREATE TABLE customers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '客户ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_no VARCHAR(64) NOT NULL COMMENT '客户编号',
    name VARCHAR(256) NOT NULL COMMENT '客户名称',
    short_name VARCHAR(128) NULL COMMENT '客户简称',
    type TINYINT NOT NULL DEFAULT 1 COMMENT '类型: 1=企业, 2=个人',
    industry VARCHAR(64) NULL COMMENT '所属行业',
    scale VARCHAR(32) NULL COMMENT '企业规模: small/medium/large',
    source VARCHAR(32) NULL COMMENT '客户来源',
    level TINYINT NOT NULL DEFAULT 1 COMMENT '客户等级: 1-5',
    rating DECIMAL(3,2) NULL COMMENT '信用评级 0.00-5.00',
    website VARCHAR(512) NULL COMMENT '官网',
    phone VARCHAR(64) NULL COMMENT '电话',
    fax VARCHAR(64) NULL COMMENT '传真',
    email VARCHAR(255) NULL COMMENT '邮箱',
    employee_count INT NULL COMMENT '员工人数',
    annual_revenue DECIMAL(15,2) NULL COMMENT '年营业额',
    credit_code VARCHAR(32) NULL COMMENT '统一社会信用代码',
    legal_person VARCHAR(64) NULL COMMENT '法人代表',
    registered_capital DECIMAL(15,2) NULL COMMENT '注册资本',
    business_scope TEXT NULL COMMENT '经营范围',
    description TEXT NULL COMMENT '备注描述',
    owner_id BIGINT NULL COMMENT '负责人(销售OWNER)',
    area VARCHAR(64) NULL COMMENT '所属区域',
    city VARCHAR(64) NULL COMMENT '所属城市',
    province VARCHAR(64) NULL COMMENT '所属省份',
    country VARCHAR(64) NOT NULL DEFAULT '中国' COMMENT '所属国家',
    latitude DECIMAL(10,6) NULL COMMENT '纬度',
    longitude DECIMAL(11,6) NULL COMMENT '经度',
    last_contact_at DATETIME NULL COMMENT '最后联系时间',
    next_followup_at DATETIME NULL COMMENT '下次联系时间',
    churn_at DATETIME NULL COMMENT '流失时间',
    churn_reason VARCHAR(255) NULL COMMENT '流失原因',
    tags VARCHAR(512) NULL COMMENT '标签(JSON数组)',
    source_id BIGINT NULL COMMENT '来源渠道ID',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 0=无效, 1=潜在, 2=正式, 3=流失, 4=已合并',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_customers_tenant_no (tenant_id, customer_no),
    INDEX idx_customers_tenant_id (tenant_id),
    INDEX idx_customers_name (name),
    INDEX idx_customers_owner_id (owner_id),
    INDEX idx_customers_level (level),
    INDEX idx_customers_industry (industry),
    INDEX idx_customers_source (source),
    INDEX idx_customers_status (status),
    INDEX idx_customers_created_at (created_at),
    INDEX idx_customers_last_contact_at (last_contact_at),
    FULLTEXT INDEX ft_customers_name (name, short_name, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户表';

-- ----------------------------
-- 2.2 客户联系人表
-- ----------------------------
CREATE TABLE customer_contacts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '联系人ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    name VARCHAR(64) NOT NULL COMMENT '姓名',
    gender TINYINT NULL COMMENT '性别: 1=男, 2=女',
    position VARCHAR(128) NULL COMMENT '职位',
    department VARCHAR(128) NULL COMMENT '部门',
    phone VARCHAR(64) NULL COMMENT '手机',
    phone2 VARCHAR(64) NULL COMMENT '备用手机',
    email VARCHAR(255) NULL COMMENT '邮箱',
    email2 VARCHAR(255) NULL COMMENT '备用邮箱',
    wechat VARCHAR(64) NULL COMMENT '微信',
    qq VARCHAR(32) NULL COMMENT 'QQ',
    birthday DATE NULL COMMENT '生日',
    hobby VARCHAR(255) NULL COMMENT '爱好',
    is_key_person TINYINT NOT NULL DEFAULT 0 COMMENT '是否关键人: 0=否, 1=是',
    is_decision_maker TINYINT NOT NULL DEFAULT 0 COMMENT '是否决策人: 0=否, 1=是',
    is_primary TINYINT NOT NULL DEFAULT 0 COMMENT '是否主联系人: 0=否, 1=是',
    is_subscribe_email TINYINT NOT NULL DEFAULT 1 COMMENT '是否订阅邮件: 0=否, 1=是',
    is_subscribe_sms TINYINT NOT NULL DEFAULT 1 COMMENT '是否订阅短信: 0=否, 1=是',
    description TEXT NULL COMMENT '备注',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_contacts_tenant_id (tenant_id),
    INDEX idx_contacts_customer_id (customer_id),
    INDEX idx_contacts_phone (phone),
    INDEX idx_contacts_email (email),
    INDEX idx_contacts_is_primary (is_primary),
    INDEX idx_contacts_is_key_person (is_key_person)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户联系人表';

-- ----------------------------
-- 2.3 客户地址表
-- ----------------------------
CREATE TABLE customer_addresses (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '地址ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    address_type TINYINT NOT NULL DEFAULT 1 COMMENT '类型: 1= billing(账单地址), 2=shipping(发货地址), 3=office(办公地址), 4=warehouse(仓库地址)',
    name VARCHAR(128) NULL COMMENT '地址名称',
    receiver VARCHAR(64) NULL COMMENT '收货人',
    phone VARCHAR(64) NULL COMMENT '联系电话',
    province VARCHAR(64) NULL COMMENT '省份',
    city VARCHAR(64) NULL COMMENT '城市',
    district VARCHAR(64) NULL COMMENT '区县',
    street VARCHAR(255) NULL COMMENT '街道',
    address VARCHAR(512) NOT NULL COMMENT '详细地址',
    postal_code VARCHAR(16) NULL COMMENT '邮政编码',
    latitude DECIMAL(10,6) NULL COMMENT '纬度',
    longitude DECIMAL(11,6) NULL COMMENT '经度',
    is_default TINYINT NOT NULL DEFAULT 0 COMMENT '是否默认: 0=否, 1=是',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_addresses_tenant_id (tenant_id),
    INDEX idx_addresses_customer_id (customer_id),
    INDEX idx_addresses_contact_id (contact_id),
    INDEX idx_addresses_is_default (is_default)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户地址表';

-- ----------------------------
-- 2.4 客户标签关联表
-- ----------------------------
CREATE TABLE customer_tags (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    tag_id BIGINT NOT NULL COMMENT '标签ID',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by BIGINT NULL COMMENT '创建人',
    UNIQUE INDEX idx_customer_tags_unique (customer_id, tag_id),
    INDEX idx_customer_tags_tenant_id (tenant_id),
    INDEX idx_customer_tags_customer_id (customer_id),
    INDEX idx_customer_tags_tag_id (tag_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户标签关联表';

-- ----------------------------
-- 2.5 标签表
-- ----------------------------
CREATE TABLE tags (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '标签ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(64) NOT NULL COMMENT '标签名称',
    code VARCHAR(64) NULL COMMENT '标签编码',
    color VARCHAR(16) NOT NULL DEFAULT '#1890ff' COMMENT '颜色',
    type VARCHAR(32) NULL COMMENT '标签类型: customer/lead/opportunity/ticket',
    description VARCHAR(255) NULL COMMENT '描述',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    usage_count INT NOT NULL DEFAULT 0 COMMENT '使用次数',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_tags_tenant_id (tenant_id),
    INDEX idx_tags_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='标签表';

-- ----------------------------
-- 2.6 客户负责人变更历史表
-- ----------------------------
CREATE TABLE customer_owner_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    old_owner_id BIGINT NULL COMMENT '原负责人',
    new_owner_id BIGINT NOT NULL COMMENT '新负责人',
    change_type VARCHAR(32) NOT NULL COMMENT '变更类型: transfer/reclaim/allocation',
    reason VARCHAR(255) NULL COMMENT '变更原因',
    transfer_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '变更时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by BIGINT NULL COMMENT '创建人',
    INDEX idx_owner_history_tenant_id (tenant_id),
    INDEX idx_owner_history_customer_id (customer_id),
    INDEX idx_owner_history_old_owner_id (old_owner_id),
    INDEX idx_owner_history_new_owner_id (new_owner_id),
    INDEX idx_owner_history_transfer_at (transfer_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户负责人变更历史表';

-- ----------------------------
-- 2.7 客户合并日志表
-- ----------------------------
CREATE TABLE customer_merge_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    source_customer_id BIGINT NOT NULL COMMENT '源客户ID(被合并)',
    target_customer_id BIGINT NOT NULL COMMENT '目标客户ID(合并到)',
    merge_type VARCHAR(32) NOT NULL COMMENT '合并类型: auto/manual',
    merge_fields JSON NULL COMMENT '合并的字段映射',
    merge_relations JSON NULL COMMENT '合并的关联记录数',
    operator_id BIGINT NOT NULL COMMENT '操作人',
    merged_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '合并时间',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_merge_log_tenant_id (tenant_id),
    INDEX idx_merge_log_source_customer_id (source_customer_id),
    INDEX idx_merge_log_target_customer_id (target_customer_id),
    INDEX idx_merge_log_merged_at (merged_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户合并日志表';

-- ----------------------------
-- 2.8 客户关注者表
-- ----------------------------
CREATE TABLE customer_followers (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    user_id BIGINT NOT NULL COMMENT '关注用户ID',
    notify_enabled TINYINT NOT NULL DEFAULT 1 COMMENT '是否开启通知: 0=否, 1=是',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    UNIQUE INDEX idx_customer_followers_unique (customer_id, user_id),
    INDEX idx_followers_tenant_id (tenant_id),
    INDEX idx_followers_customer_id (customer_id),
    INDEX idx_followers_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户关注者表';

-- ----------------------------
-- 2.9 客户自定义字段定义表
-- ----------------------------
CREATE TABLE customer_custom_fields (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '字段ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    field_name VARCHAR(64) NOT NULL COMMENT '字段名称(英文)',
    field_label VARCHAR(128) NOT NULL COMMENT '字段标签(中文)',
    field_type VARCHAR(32) NOT NULL COMMENT '字段类型: text/textarea/number/select/multi_select/date/datetime/checkbox/radio/attachment/link/phone',
    field_options JSON NULL COMMENT '字段选项(JSON数组，用于select/radio类型)',
    field_length INT NULL COMMENT '字段长度',
    is_required TINYINT NOT NULL DEFAULT 0 COMMENT '是否必填: 0=否, 1=是',
    is_unique TINYINT NOT NULL DEFAULT 0 COMMENT '是否唯一: 0=否, 1=是',
    is_searchable TINYINT NOT NULL DEFAULT 1 COMMENT '是否可搜索: 0=否, 1=是',
    is_list_show TINYINT NOT NULL DEFAULT 1 COMMENT '是否列表显示: 0=否, 1=是',
    is_filterable TINYINT NOT NULL DEFAULT 1 COMMENT '是否可筛选: 0=否, 1=是',
    default_value VARCHAR(512) NULL COMMENT '默认值',
    placeholder VARCHAR(256) NULL COMMENT '占位符',
    validation_rule VARCHAR(512) NULL COMMENT '验证规则',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    group_name VARCHAR(64) NULL COMMENT '字段分组',
    help_text VARCHAR(512) NULL COMMENT '帮助文本',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_custom_fields_tenant_field_name (tenant_id, field_name),
    INDEX idx_custom_fields_tenant_id (tenant_id),
    INDEX idx_custom_fields_field_type (field_type),
    INDEX idx_custom_fields_sort_order (sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户自定义字段定义表';

-- ----------------------------
-- 2.10 客户自定义字段值表
-- ----------------------------
CREATE TABLE customer_field_values (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    field_id BIGINT NOT NULL COMMENT '字段ID',
    field_value TEXT NULL COMMENT '字段值',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE INDEX idx_field_values_unique (customer_id, field_id),
    INDEX idx_field_values_tenant_id (tenant_id),
    INDEX idx_field_values_customer_id (customer_id),
    INDEX idx_field_values_field_id (field_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='客户自定义字段值表';

-- =============================================================================
-- 3. 销售与商机（10张表）
-- =============================================================================

-- ----------------------------
-- 3.1 线索表
-- ----------------------------
CREATE TABLE leads (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '线索ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    lead_no VARCHAR(64) NOT NULL COMMENT '线索编号',
    name VARCHAR(256) NOT NULL COMMENT '姓名/公司名',
    phone VARCHAR(64) NULL COMMENT '手机',
    email VARCHAR(255) NULL COMMENT '邮箱',
    wechat VARCHAR(64) NULL COMMENT '微信',
    qq VARCHAR(32) NULL COMMENT 'QQ',
    company VARCHAR(256) NULL COMMENT '公司名称',
    position VARCHAR(128) NULL COMMENT '职位',
    industry VARCHAR(64) NULL COMMENT '行业',
    source VARCHAR(64) NULL COMMENT '来源渠道',
    source_id BIGINT NULL COMMENT '来源ID',
    medium VARCHAR(64) NULL COMMENT '媒介',
    campaign VARCHAR(128) NULL COMMENT '营销活动',
    referer_url VARCHAR(512) NULL COMMENT '来源URL',
    interest_level TINYINT NULL COMMENT '意向等级: 1-5',
    budget DECIMAL(15,2) NULL COMMENT '预算',
    purchase_timeline VARCHAR(64) NULL COMMENT '购买时间线',
    purchase_plan VARCHAR(128) NULL COMMENT '购买计划',
    description TEXT NULL COMMENT '备注描述',
    owner_id BIGINT NULL COMMENT '负责人',
    assigned_at DATETIME NULL COMMENT '分配时间',
    converted_at DATETIME NULL COMMENT '转化时间',
    converted_customer_id BIGINT NULL COMMENT '转化客户ID',
    tags VARCHAR(512) NULL COMMENT '标签(JSON数组)',
    status TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1=新线索, 2=已分配, 3=跟进中, 4=已转化, 5=已放弃',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_leads_tenant_no (tenant_id, lead_no),
    INDEX idx_leads_tenant_id (tenant_id),
    INDEX idx_leads_phone (phone),
    INDEX idx_leads_email (email),
    INDEX idx_leads_owner_id (owner_id),
    INDEX idx_leads_source (source),
    INDEX idx_leads_status (status),
    INDEX idx_leads_created_at (created_at),
    FULLTEXT INDEX ft_leads_name (name, company, description)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='线索表';

-- ----------------------------
-- 3.2 线索来源表
-- ----------------------------
CREATE TABLE lead_sources (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '来源ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(128) NOT NULL COMMENT '来源名称',
    code VARCHAR(64) NOT NULL COMMENT '来源编码',
    type VARCHAR(32) NULL COMMENT '来源类型: offline/online/partner',
    cost_per_lead DECIMAL(10,2) NULL COMMENT '线索成本',
    is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用: 0=否, 1=是',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_lead_sources_tenant_id (tenant_id),
    INDEX idx_lead_sources_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='线索来源表';

-- ----------------------------
-- 3.3 线索分配表
-- ----------------------------
CREATE TABLE lead_assignments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分配ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    lead_id BIGINT NOT NULL COMMENT '线索ID',
    assign_type VARCHAR(32) NOT NULL COMMENT '分配方式: auto/manual/round_robin/load_balance',
    old_owner_id BIGINT NULL COMMENT '原负责人',
    new_owner_id BIGINT NOT NULL COMMENT '新负责人',
    assign_rule_id BIGINT NULL COMMENT '分配规则ID',
    priority INT NOT NULL DEFAULT 0 COMMENT '优先级',
    assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '分配时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by BIGINT NULL COMMENT '创建人',
    INDEX idx_assignments_tenant_id (tenant_id),
    INDEX idx_assignments_lead_id (lead_id),
    INDEX idx_assignments_old_owner_id (old_owner_id),
    INDEX idx_assignments_new_owner_id (new_owner_id),
    INDEX idx_assignments_assign_type (assign_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='线索分配表';

-- ----------------------------
-- 3.4 商机表
-- ----------------------------
CREATE TABLE opportunities (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '商机ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    opportunity_no VARCHAR(64) NOT NULL COMMENT '商机编号',
    name VARCHAR(256) NOT NULL COMMENT '商机名称',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    stage_id BIGINT NOT NULL COMMENT '销售阶段ID',
    stage_name VARCHAR(64) NOT NULL COMMENT '阶段名称(冗余)',
    stage_sort_order INT NOT NULL DEFAULT 0 COMMENT '阶段排序(冗余)',
    probability DECIMAL(5,2) NULL COMMENT '赢单概率',
    amount DECIMAL(15,2) NOT NULL DEFAULT 0 COMMENT '商机金额',
    discounted_amount DECIMAL(15,2) NULL COMMENT '折扣后金额',
    cost DECIMAL(15,2) NULL COMMENT '成本',
    expected_close_date DATE NULL COMMENT '预计成交日期',
    actual_close_date DATE NULL COMMENT '实际成交日期',
    close_reason VARCHAR(128) NULL COMMENT '成交/失败原因',
    lost_competitor VARCHAR(128) NULL COMMENT '输给了哪个竞品',
    lead_source VARCHAR(64) NULL COMMENT '来源渠道',
    lead_id BIGINT NULL COMMENT '线索ID',
    campaign_id BIGINT NULL COMMENT '营销活动ID',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    team_id BIGINT NULL COMMENT '销售团队ID',
    is_locked TINYINT NOT NULL DEFAULT 0 COMMENT '是否锁定: 0=否, 1=是',
    locked_reason VARCHAR(255) NULL COMMENT '锁定原因',
    tags VARCHAR(512) NULL COMMENT '标签(JSON数组)',
    next_followup_at DATETIME NULL COMMENT '下次跟进时间',
    last_followup_at DATETIME NULL COMMENT '最后跟进时间',
    followup_count INT NOT NULL DEFAULT 0 COMMENT '跟进次数',
    type VARCHAR(32) NULL COMMENT '商机类型: new/expansion/renewal',
    source VARCHAR(32) NULL COMMENT '来源: self_develop/existing_customer/partner',
    win_rate DECIMAL(5,2) NULL COMMENT '历史赢单率',
    description TEXT NULL COMMENT '备注描述',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_opportunities_tenant_no (tenant_id, opportunity_no),
    INDEX idx_opportunities_tenant_id (tenant_id),
    INDEX idx_opportunities_customer_id (customer_id),
    INDEX idx_opportunities_stage_id (stage_id),
    INDEX idx_opportunities_owner_id (owner_id),
    INDEX idx_opportunities_amount (amount),
    INDEX idx_opportunities_expected_close_date (expected_close_date),
    INDEX idx_opportunities_status (stage_sort_order),
    INDEX idx_opportunities_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商机表';

-- ----------------------------
-- 3.5 商机阶段表
-- ----------------------------
CREATE TABLE opportunity_stages (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '阶段ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(64) NOT NULL COMMENT '阶段名称',
    code VARCHAR(32) NOT NULL COMMENT '阶段编码',
    probability DECIMAL(5,2) NOT NULL COMMENT '赢单概率',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    duration_days INT NULL COMMENT '建议周期(天)',
    is_default TINYINT NOT NULL DEFAULT 0 COMMENT '是否默认: 0=否, 1=是',
    is_won TINYINT NOT NULL DEFAULT 0 COMMENT '是否成交阶段: 0=否, 1=是',
    is_lost TINYINT NOT NULL DEFAULT 0 COMMENT '是否输单阶段: 0=否, 1=是',
    description VARCHAR(255) NULL COMMENT '阶段描述',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_stages_tenant_id (tenant_id),
    INDEX idx_stages_is_won (is_won),
    INDEX idx_stages_is_lost (is_lost)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商机阶段表';

-- ----------------------------
-- 3.6 商机阶段变更历史表
-- ----------------------------
CREATE TABLE opportunity_stage_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    opportunity_id BIGINT NOT NULL COMMENT '商机ID',
    from_stage_id BIGINT NULL COMMENT '原阶段ID',
    from_stage_name VARCHAR(64) NULL COMMENT '原阶段名称',
    to_stage_id BIGINT NOT NULL COMMENT '新阶段ID',
    to_stage_name VARCHAR(64) NOT NULL COMMENT '新阶段名称',
    from_probability DECIMAL(5,2) NULL COMMENT '原概率',
    to_probability DECIMAL(5,2) NULL COMMENT '新概率',
    from_amount DECIMAL(15,2) NULL COMMENT '原金额',
    to_amount DECIMAL(15,2) NULL COMMENT '新金额',
    change_type VARCHAR(32) NOT NULL COMMENT '变更类型: manual/auto/migration',
    operator_id BIGINT NOT NULL COMMENT '操作人',
    reason VARCHAR(255) NULL COMMENT '变更原因',
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '变更时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_stage_history_tenant_id (tenant_id),
    INDEX idx_stage_history_opportunity_id (opportunity_id),
    INDEX idx_stage_history_from_stage_id (from_stage_id),
    INDEX idx_stage_history_to_stage_id (to_stage_id),
    INDEX idx_stage_history_operator_id (operator_id),
    INDEX idx_stage_history_changed_at (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商机阶段变更历史表';

-- ----------------------------
-- 3.7 商机产品关联表
-- ----------------------------
CREATE TABLE opportunity_products (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    opportunity_id BIGINT NOT NULL COMMENT '商机ID',
    product_id BIGINT NOT NULL COMMENT '产品ID',
    product_name VARCHAR(256) NOT NULL COMMENT '产品名称(冗余)',
    sku_code VARCHAR(64) NULL COMMENT 'SKU编码',
    quantity INT NOT NULL DEFAULT 1 COMMENT '数量',
    unit_price DECIMAL(15,4) NULL COMMENT '单价',
    cost_price DECIMAL(15,4) NULL COMMENT '成本价',
    discount_rate DECIMAL(5,4) NULL COMMENT '折扣率',
    tax_rate DECIMAL(5,4) NULL COMMENT '税率',
    tax_amount DECIMAL(15,4) NULL COMMENT '税额',
    subtotal DECIMAL(15,4) NULL COMMENT '小计',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    description TEXT NULL COMMENT '产品说明',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_opportunity_products_tenant_id (tenant_id),
    INDEX idx_opportunity_products_opportunity_id (opportunity_id),
    INDEX idx_opportunity_products_product_id (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商机产品关联表';

-- ----------------------------
-- 3.8 报价单表
-- ----------------------------
CREATE TABLE quotes (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '报价ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    quote_no VARCHAR(64) NOT NULL COMMENT '报价单号',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    title VARCHAR(256) NOT NULL COMMENT '报价标题',
    version INT NOT NULL DEFAULT 1 COMMENT '版本号',
    status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态: draft/pending/approved/sent/accepted/rejected/expired/void',
    valid_from DATE NULL COMMENT '有效期开始',
    valid_until DATE NULL COMMENT '有效期截止',
    subtotal DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '合计金额',
    discount_rate DECIMAL(5,4) NULL COMMENT '折扣率',
    discount_amount DECIMAL(15,4) NULL COMMENT '折扣金额',
    tax_rate DECIMAL(5,4) NULL COMMENT '税率',
    tax_amount DECIMAL(15,4) NULL COMMENT '税额',
    total_amount DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '总金额',
    payment_terms VARCHAR(128) NULL COMMENT '付款条款',
    delivery_terms VARCHAR(128) NULL COMMENT '交货条款',
    warranty_terms VARCHAR(256) NULL COMMENT '质保条款',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    approver_id BIGINT NULL COMMENT '审批人',
    approved_at DATETIME NULL COMMENT '审批时间',
    sent_at DATETIME NULL COMMENT '发送时间',
    signed_at DATETIME NULL COMMENT '签收时间',
    currency VARCHAR(8) NOT NULL DEFAULT 'CNY' COMMENT '币种',
    exchange_rate DECIMAL(10,6) NOT NULL DEFAULT 1 COMMENT '汇率',
    bank_info TEXT NULL COMMENT '银行信息',
    description TEXT NULL COMMENT '备注描述',
    terms TEXT NULL COMMENT '条款正文',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_quotes_tenant_no (tenant_id, quote_no),
    INDEX idx_quotes_tenant_id (tenant_id),
    INDEX idx_quotes_opportunity_id (opportunity_id),
    INDEX idx_quotes_customer_id (customer_id),
    INDEX idx_quotes_status (status),
    INDEX idx_quotes_owner_id (owner_id),
    INDEX idx_quotes_valid_until (valid_until)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报价单表';

-- ----------------------------
-- 3.9 报价明细表
-- ----------------------------
CREATE TABLE quote_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '明细ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    quote_id BIGINT NOT NULL COMMENT '报价ID',
    product_id BIGINT NULL COMMENT '产品ID',
    product_name VARCHAR(256) NOT NULL COMMENT '产品名称',
    sku_code VARCHAR(64) NULL COMMENT 'SKU编码',
    specification VARCHAR(512) NULL COMMENT '规格型号',
    unit VARCHAR(32) NULL COMMENT '单位',
    quantity DECIMAL(15,4) NOT NULL DEFAULT 1 COMMENT '数量',
    unit_price DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '单价',
    cost_price DECIMAL(15,4) NULL COMMENT '成本价',
    discount_rate DECIMAL(5,4) NULL COMMENT '折扣率',
    tax_rate DECIMAL(5,4) NULL COMMENT '税率',
    tax_amount DECIMAL(15,4) NULL COMMENT '税额',
    subtotal DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '小计金额',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    description TEXT NULL COMMENT '项目描述',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_quote_items_tenant_id (tenant_id),
    INDEX idx_quote_items_quote_id (quote_id),
    INDEX idx_quote_items_product_id (product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='报价明细表';

-- ----------------------------
-- 3.10 合同表
-- ----------------------------
CREATE TABLE contracts (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '合同ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    contract_no VARCHAR(64) NOT NULL COMMENT '合同编号',
    title VARCHAR(256) NOT NULL COMMENT '合同名称',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    customer_id BIGINT NOT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    quote_id BIGINT NULL COMMENT '关联报价ID',
    amount DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '合同金额',
    received_amount DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '已收款金额',
    pending_amount DECIMAL(15,4) NOT NULL DEFAULT 0 COMMENT '待收款金额',
    sign_date DATE NULL COMMENT '签订日期',
    start_date DATE NULL COMMENT '开始日期',
    end_date DATE NULL COMMENT '结束日期',
    status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态: draft/active/pending/completed/terminated/cancelled',
    payment_status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '付款状态: pending/partial/paid/overdue',
    payment_terms VARCHAR(128) NULL COMMENT '付款方式',
    delivery_terms VARCHAR(128) NULL COMMENT '交货条款',
    warranty_months INT NULL COMMENT '质保期(月)',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    approver_id BIGINT NULL COMMENT '审批人',
    approved_at DATETIME NULL COMMENT '审批时间',
    signed_at DATETIME NULL COMMENT '签署时间',
    currency VARCHAR(8) NOT NULL DEFAULT 'CNY' COMMENT '币种',
    attachment_urls JSON NULL COMMENT '附件URL列表',
    terms TEXT NULL COMMENT '合同条款',
    description TEXT NULL COMMENT '备注描述',
    auto_renew TINYINT NOT NULL DEFAULT 0 COMMENT '是否自动续约: 0=否, 1=是',
    renew_notice_days INT NOT NULL DEFAULT 30 COMMENT '续约提前通知天数',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_contracts_tenant_no (tenant_id, contract_no),
    INDEX idx_contracts_tenant_id (tenant_id),
    INDEX idx_contracts_opportunity_id (opportunity_id),
    INDEX idx_contracts_customer_id (customer_id),
    INDEX idx_contracts_status (status),
    INDEX idx_contracts_payment_status (payment_status),
    INDEX idx_contracts_owner_id (owner_id),
    INDEX idx_contracts_sign_date (sign_date),
    INDEX idx_contracts_end_date (end_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='合同表';

-- =============================================================================
-- 4. 跟进与任务（10张表）
-- =============================================================================

-- ----------------------------
-- 4.1 跟进活动表
-- ----------------------------
CREATE TABLE activities (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '跟进ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    activity_type_id BIGINT NOT NULL COMMENT '活动类型ID',
    activity_type_name VARCHAR(64) NOT NULL COMMENT '活动类型名称(冗余)',
    subject VARCHAR(256) NOT NULL COMMENT '主题',
    content TEXT NULL COMMENT '内容',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    task_id BIGINT NULL COMMENT '关联任务ID',
    is_done TINYINT NOT NULL DEFAULT 0 COMMENT '是否完成: 0=否, 1=是',
    done_at DATETIME NULL COMMENT '完成时间',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    participant_ids JSON NULL COMMENT '参与人ID列表',
    location VARCHAR(256) NULL COMMENT '地点',
    latitude DECIMAL(10,6) NULL COMMENT '纬度',
    longitude DECIMAL(11,6) NULL COMMENT '经度',
    start_at DATETIME NULL COMMENT '开始时间',
    end_at DATETIME NULL COMMENT '结束时间',
    duration INT NULL COMMENT '时长(分钟)',
    priority TINYINT NOT NULL DEFAULT 2 COMMENT '优先级: 1=高, 2=中, 3=低',
    feedback TEXT NULL COMMENT '跟进反馈',
    next_followup_at DATETIME NULL COMMENT '下次跟进时间',
    attachments JSON NULL COMMENT '附件列表',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_activities_tenant_id (tenant_id),
    INDEX idx_activities_type_id (activity_type_id),
    INDEX idx_activities_customer_id (customer_id),
    INDEX idx_activities_lead_id (lead_id),
    INDEX idx_activities_opportunity_id (opportunity_id),
    INDEX idx_activities_contact_id (contact_id),
    INDEX idx_activities_owner_id (owner_id),
    INDEX idx_activities_is_done (is_done),
    INDEX idx_activities_start_at (start_at),
    INDEX idx_activities_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='跟进活动表';

-- ----------------------------
-- 4.2 活动类型表
-- ----------------------------
CREATE TABLE activity_types (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '类型ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(64) NOT NULL COMMENT '类型名称',
    code VARCHAR(32) NOT NULL COMMENT '类型编码',
    icon VARCHAR(32) NULL COMMENT '图标',
    color VARCHAR(16) NULL COMMENT '颜色',
    is_system TINYINT NOT NULL DEFAULT 0 COMMENT '是否系统类型: 0=否, 1=是',
    is_calendar TINYINT NOT NULL DEFAULT 1 COMMENT '是否日历类型: 0=否, 1=是',
    duration INT NULL COMMENT '默认时长(分钟)',
    description VARCHAR(255) NULL COMMENT '描述',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_activity_types_tenant_id (tenant_id),
    INDEX idx_activity_types_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='活动类型表';

-- ----------------------------
-- 4.3 任务表
-- ----------------------------
CREATE TABLE tasks (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '任务ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    task_no VARCHAR(64) NOT NULL COMMENT '任务编号',
    subject VARCHAR(256) NOT NULL COMMENT '任务主题',
    content TEXT NULL COMMENT '任务内容',
    task_type VARCHAR(32) NOT NULL COMMENT '任务类型: follow_up/call/meeting/todo',
    priority TINYINT NOT NULL DEFAULT 2 COMMENT '优先级: 1=高, 2=中, 3=低',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/in_progress/completed/cancelled',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    assignee_id BIGINT NULL COMMENT '受让人',
    due_date DATETIME NULL COMMENT '截止日期',
    completed_at DATETIME NULL COMMENT '完成时间',
    reminder_at DATETIME NULL COMMENT '提醒时间',
    is_recurring TINYINT NOT NULL DEFAULT 0 COMMENT '是否重复: 0=否, 1=是',
    recurring_pattern VARCHAR(64) NULL COMMENT '重复模式',
    parent_id BIGINT NULL COMMENT '父任务ID',
    completion_rate INT NOT NULL DEFAULT 0 COMMENT '完成进度 0-100',
    tags VARCHAR(512) NULL COMMENT '标签(JSON数组)',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_tasks_tenant_no (tenant_id, task_no),
    INDEX idx_tasks_tenant_id (tenant_id),
    INDEX idx_tasks_customer_id (customer_id),
    INDEX idx_tasks_lead_id (lead_id),
    INDEX idx_tasks_opportunity_id (opportunity_id),
    INDEX idx_tasks_owner_id (owner_id),
    INDEX idx_tasks_assignee_id (assignee_id),
    INDEX idx_tasks_status (status),
    INDEX idx_tasks_priority (priority),
    INDEX idx_tasks_due_date (due_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- ----------------------------
-- 4.4 任务评论表
-- ----------------------------
CREATE TABLE task_comments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '评论ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    task_id BIGINT NOT NULL COMMENT '任务ID',
    content TEXT NOT NULL COMMENT '评论内容',
    parent_id BIGINT NULL COMMENT '父评论ID',
    reply_to_id BIGINT NULL COMMENT '回复ID',
    is_internal TINYINT NOT NULL DEFAULT 0 COMMENT '是否内部评论: 0=否, 1=是',
    attachments JSON NULL COMMENT '附件',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_task_comments_tenant_id (tenant_id),
    INDEX idx_task_comments_task_id (task_id),
    INDEX idx_task_comments_parent_id (parent_id),
    INDEX idx_task_comments_created_by (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务评论表';

-- ----------------------------
-- 4.5 会议表
-- ----------------------------
CREATE TABLE meetings (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '会议ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    meeting_no VARCHAR(64) NOT NULL COMMENT '会议编号',
    title VARCHAR(256) NOT NULL COMMENT '会议主题',
    content TEXT NULL COMMENT '会议内容/议程',
    meeting_type VARCHAR(32) NULL COMMENT '会议类型: online/offline',
    location VARCHAR(256) NULL COMMENT '会议地点',
    online_url VARCHAR(512) NULL COMMENT '线上会议链接',
    host_id BIGINT NOT NULL COMMENT '主持人',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    start_at DATETIME NOT NULL COMMENT '开始时间',
    end_at DATETIME NOT NULL COMMENT '结束时间',
    duration INT NOT NULL COMMENT '时长(分钟)',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    is_recurring TINYINT NOT NULL DEFAULT 0 COMMENT '是否重复: 0=否, 1=是',
    recurring_pattern VARCHAR(64) NULL COMMENT '重复模式',
    reminder_minutes INT NULL COMMENT '提前提醒分钟数',
    status VARCHAR(32) NOT NULL DEFAULT 'scheduled' COMMENT '状态: scheduled/started/ended/cancelled',
    minutes TEXT NULL COMMENT '会议纪要',
    attachments JSON NULL COMMENT '附件',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_meetings_tenant_no (tenant_id, meeting_no),
    INDEX idx_meetings_tenant_id (tenant_id),
    INDEX idx_meetings_host_id (host_id),
    INDEX idx_meetings_owner_id (owner_id),
    INDEX idx_meetings_start_at (start_at),
    INDEX idx_meetings_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会议表';

-- ----------------------------
-- 4.6 通话记录表
-- ----------------------------
CREATE TABLE call_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '通话ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    call_no VARCHAR(64) NOT NULL COMMENT '通话编号',
    call_type VARCHAR(32) NOT NULL COMMENT '通话类型: outbound/inbound',
    direction VARCHAR(16) NOT NULL COMMENT '方向: outbound/inbound',
    status VARCHAR(32) NOT NULL COMMENT '状态: completed/missed/voicemail/cancelled',
    customer_id BIGINT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    caller_number VARCHAR(32) NULL COMMENT '主叫号码',
    callee_number VARCHAR(32) NULL COMMENT '被叫号码',
    call_start_at DATETIME NULL COMMENT '通话开始时间',
    call_end_at DATETIME NULL COMMENT '通话结束时间',
    call_duration INT NULL COMMENT '通话时长(秒)',
    wait_duration INT NULL COMMENT '等待时长(秒)',
    recording_url VARCHAR(512) NULL COMMENT '录音URL',
    summary TEXT NULL COMMENT '通话小结',
    disposition VARCHAR(64) NULL COMMENT '通话结果',
    is_follow_up TINYINT NOT NULL DEFAULT 0 COMMENT '是否有后续跟进: 0=否, 1=是',
    follow_up_task_id BIGINT NULL COMMENT '关联跟进任务ID',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_call_logs_tenant_id (tenant_id),
    INDEX idx_call_logs_customer_id (customer_id),
    INDEX idx_call_logs_contact_id (contact_id),
    INDEX idx_call_logs_owner_id (owner_id),
    INDEX idx_call_logs_call_type (call_type),
    INDEX idx_call_logs_status (status),
    INDEX idx_call_logs_call_start_at (call_start_at),
    FULLTEXT INDEX ft_call_logs_summary (summary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='通话记录表';

-- ----------------------------
-- 4.7 邮件日志表
-- ----------------------------
CREATE TABLE email_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '邮件ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    message_id VARCHAR(255) NOT NULL COMMENT '邮件Message-ID',
    customer_id BIGINT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    from_address VARCHAR(255) NOT NULL COMMENT '发件人',
    to_address TEXT NOT NULL COMMENT '收件人',
    cc_address TEXT NULL COMMENT '抄送',
    bcc_address TEXT NULL COMMENT '密送',
    subject VARCHAR(512) NOT NULL COMMENT '主题',
    body TEXT NULL COMMENT '邮件正文',
    body_html TEXT NULL COMMENT 'HTML正文',
    status VARCHAR(32) NOT NULL COMMENT '状态: pending/sent/delivered/opened/clicked/bounced/complained',
    sent_at DATETIME NULL COMMENT '发送时间',
    delivered_at DATETIME NULL COMMENT '送达时间',
    opened_at DATETIME NULL COMMENT '打开时间',
    clicked_at DATETIME NULL COMMENT '点击时间',
    bounced_at DATETIME NULL COMMENT '退信时间',
    bounce_reason VARCHAR(255) NULL COMMENT '退信原因',
    template_id BIGINT NULL COMMENT '邮件模板ID',
    template_version INT NULL COMMENT '模板版本',
    campaign_id BIGINT NULL COMMENT '营销活动ID',
    attachments JSON NULL COMMENT '附件列表',
    tracking_id VARCHAR(64) NULL COMMENT '追踪ID',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_email_logs_tenant_id (tenant_id),
    INDEX idx_email_logs_customer_id (customer_id),
    INDEX idx_email_logs_contact_id (contact_id),
    INDEX idx_email_logs_message_id (message_id),
    INDEX idx_email_logs_status (status),
    INDEX idx_email_logs_sent_at (sent_at),
    INDEX idx_email_logs_tracking_id (tracking_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邮件日志表';

-- ----------------------------
-- 4.8 提醒表
-- ----------------------------
CREATE TABLE reminders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '提醒ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    user_id BIGINT NOT NULL COMMENT '用户ID(被提醒人)',
    remind_type VARCHAR(32) NOT NULL COMMENT '提醒类型: customer/lead/opportunity/task/meeting',
    related_id BIGINT NOT NULL COMMENT '关联记录ID',
    subject VARCHAR(256) NOT NULL COMMENT '提醒主题',
    content TEXT NULL COMMENT '提醒内容',
    remind_at DATETIME NOT NULL COMMENT '提醒时间',
    is_repeated TINYINT NOT NULL DEFAULT 0 COMMENT '是否重复: 0=否, 1=是',
    repeat_pattern VARCHAR(64) NULL COMMENT '重复模式',
    is_snoozed TINYINT NOT NULL DEFAULT 0 COMMENT '是否已延迟: 0=否, 1=是',
    snooze_until DATETIME NULL COMMENT '延迟到',
    is_completed TINYINT NOT NULL DEFAULT 0 COMMENT '是否完成: 0=否, 1=是',
    completed_at DATETIME NULL COMMENT '完成时间',
    notification_channel VARCHAR(32) NULL COMMENT '通知渠道: in_app/email/sms/push',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_reminders_tenant_id (tenant_id),
    INDEX idx_reminders_user_id (user_id),
    INDEX idx_reminders_related_id (related_id),
    INDEX idx_reminders_remind_at (remind_at),
    INDEX idx_reminders_is_completed (is_completed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提醒表';

-- ----------------------------
-- 4.9 日历事件表
-- ----------------------------
CREATE TABLE calendar_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '事件ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    user_id BIGINT NOT NULL COMMENT '用户ID',
    event_no VARCHAR(64) NOT NULL COMMENT '事件编号',
    title VARCHAR(256) NOT NULL COMMENT '事件标题',
    description TEXT NULL COMMENT '事件描述',
    event_type VARCHAR(32) NOT NULL COMMENT '事件类型: meeting/call/task/reminder/deadline',
    location VARCHAR(256) NULL COMMENT '地点',
    online_url VARCHAR(512) NULL COMMENT '线上链接',
    start_at DATETIME NOT NULL COMMENT '开始时间',
    end_at DATETIME NOT NULL COMMENT '结束时间',
    is_all_day TINYINT NOT NULL DEFAULT 0 COMMENT '是否全天: 0=否, 1=是',
    is_recurring TINYINT NOT NULL DEFAULT 0 COMMENT '是否重复: 0=否, 1=是',
    recurring_pattern VARCHAR(64) NULL COMMENT '重复模式',
    recurring_end_date DATE NULL COMMENT '重复结束日期',
    reminder_minutes INT NULL COMMENT '提前提醒分钟数',
    visibility VARCHAR(16) NOT NULL DEFAULT 'private' COMMENT '可见性: public/private/confidential',
    show_as VARCHAR(16) NOT NULL DEFAULT 'busy' COMMENT '显示为: free/busy/tentative',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    opportunity_id BIGINT NULL COMMENT '商机ID',
    task_id BIGINT NULL COMMENT '关联任务ID',
    status VARCHAR(32) NOT NULL DEFAULT 'confirmed' COMMENT '状态: confirmed/cancelled/tentative',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_calendar_events_tenant_no (tenant_id, event_no),
    INDEX idx_calendar_events_tenant_id (tenant_id),
    INDEX idx_calendar_events_user_id (user_id),
    INDEX idx_calendar_events_start_at (start_at),
    INDEX idx_calendar_events_end_at (end_at),
    INDEX idx_calendar_events_customer_id (customer_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='日历事件表';

-- ----------------------------
-- 4.10 事件参与者表
-- ----------------------------
CREATE TABLE event_attendees (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    event_id BIGINT NOT NULL COMMENT '事件ID',
    user_id BIGINT NULL COMMENT '用户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    attendee_name VARCHAR(128) NULL COMMENT '参与者名称',
    attendee_email VARCHAR(255) NULL COMMENT '参与者邮箱',
    attendee_type VARCHAR(32) NOT NULL DEFAULT 'required' COMMENT '参与类型: required/optional/Chair',
    response_status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '响应状态: pending/accepted/declined/tentative',
    response_at DATETIME NULL COMMENT '响应时间',
    is_organizer TINYINT NOT NULL DEFAULT 0 COMMENT '是否组织者: 0=否, 1=是',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_event_attendees_tenant_id (tenant_id),
    INDEX idx_event_attendees_event_id (event_id),
    INDEX idx_event_attendees_user_id (user_id),
    INDEX idx_event_attendees_contact_id (contact_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='事件参与者表';

-- =============================================================================
-- 5. 营销自动化（8张表）
-- =============================================================================

-- ----------------------------
-- 5.1 营销活动表
-- ----------------------------
CREATE TABLE campaigns (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '活动ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    campaign_no VARCHAR(64) NOT NULL COMMENT '活动编号',
    name VARCHAR(256) NOT NULL COMMENT '活动名称',
    type VARCHAR(32) NOT NULL COMMENT '活动类型: email/sms/social/event/webinar/other',
    status VARCHAR(32) NOT NULL DEFAULT 'draft' COMMENT '状态: draft/active/paused/completed/cancelled',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    budget DECIMAL(15,2) NULL COMMENT '预算',
    actual_cost DECIMAL(15,2) NULL COMMENT '实际花费',
    start_at DATETIME NULL COMMENT '开始时间',
    end_at DATETIME NULL COMMENT '结束时间',
    target_audience JSON NULL COMMENT '目标受众定义',
    description TEXT NULL COMMENT '活动描述',
    channel VARCHAR(64) NULL COMMENT '营销渠道',
    utm_source VARCHAR(128) NULL COMMENT 'UTM来源',
    utm_medium VARCHAR(128) NULL COMMENT 'UTM媒介',
    utm_campaign VARCHAR(128) NULL COMMENT 'UTM活动',
    utm_content VARCHAR(256) NULL COMMENT 'UTM内容',
    utm_term VARCHAR(256) NULL COMMENT 'UTM关键词',
    track_links TINYINT NOT NULL DEFAULT 1 COMMENT '是否追踪链接: 0=否, 1=是',
    results JSON NULL COMMENT '营销结果统计',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_campaigns_tenant_no (tenant_id, campaign_no),
    INDEX idx_campaigns_tenant_id (tenant_id),
    INDEX idx_campaigns_type (type),
    INDEX idx_campaigns_status (status),
    INDEX idx_campaigns_owner_id (owner_id),
    INDEX idx_campaigns_start_at (start_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='营销活动表';

-- ----------------------------
-- 5.2 营销活动成员表
-- ----------------------------
CREATE TABLE campaign_members (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    campaign_id BIGINT NOT NULL COMMENT '活动ID',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    email VARCHAR(255) NULL COMMENT '邮箱地址',
    phone VARCHAR(64) NULL COMMENT '电话',
    name VARCHAR(128) NULL COMMENT '姓名',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/active/converted/unsubscribed/bounced',
    joined_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '加入时间',
    last_sent_at DATETIME NULL COMMENT '最后发送时间',
    sent_count INT NOT NULL DEFAULT 0 COMMENT '发送次数',
    opened_count INT NOT NULL DEFAULT 0 COMMENT '打开次数',
    clicked_count INT NOT NULL DEFAULT 0 COMMENT '点击次数',
    converted_at DATETIME NULL COMMENT '转化时间',
    converted_type VARCHAR(32) NULL COMMENT '转化类型',
    converted_id BIGINT NULL COMMENT '转化ID',
    unsubscribed_at DATETIME NULL COMMENT '退订时间',
    bounced_at DATETIME NULL COMMENT '退信时间',
    bounced_reason VARCHAR(255) NULL COMMENT '退信原因',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_campaign_members_tenant_id (tenant_id),
    INDEX idx_campaign_members_campaign_id (campaign_id),
    INDEX idx_campaign_members_customer_id (customer_id),
    INDEX idx_campaign_members_lead_id (lead_id),
    INDEX idx_campaign_members_email (email),
    INDEX idx_campaign_members_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='营销活动成员表';

-- ----------------------------
-- 5.3 邮件模板表
-- ----------------------------
CREATE TABLE email_templates (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '模板ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(128) NOT NULL COMMENT '模板名称',
    code VARCHAR(64) NOT NULL COMMENT '模板编码',
    category VARCHAR(32) NULL COMMENT '模板分类',
    subject VARCHAR(512) NOT NULL COMMENT '邮件主题',
    body TEXT NOT NULL COMMENT '邮件正文',
    body_html TEXT NULL COMMENT 'HTML正文',
    preheader_text VARCHAR(256) NULL COMMENT '预header文字',
    sender_name VARCHAR(128) NULL COMMENT '发件人名称',
    sender_email VARCHAR(255) NULL COMMENT '发件人邮箱',
    reply_to VARCHAR(255) NULL COMMENT '回复邮箱',
    tags JSON NULL COMMENT '标签',
    variables JSON NULL COMMENT '可用变量定义',
    is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用: 0=否, 1=是',
    is_system TINYINT NOT NULL DEFAULT 0 COMMENT '是否系统模板: 0=否, 1=是',
    version INT NOT NULL DEFAULT 1 COMMENT '版本号',
    usage_count INT NOT NULL DEFAULT 0 COMMENT '使用次数',
    last_used_at DATETIME NULL COMMENT '最后使用时间',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_email_templates_tenant_id (tenant_id),
    INDEX idx_email_templates_code (code),
    INDEX idx_email_templates_category (category),
    INDEX idx_email_templates_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邮件模板表';

-- ----------------------------
-- 5.4 邮件发送记录表
-- ----------------------------
CREATE TABLE email_sends (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '发送ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    campaign_id BIGINT NULL COMMENT '营销活动ID',
    template_id BIGINT NULL COMMENT '邮件模板ID',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    recipient_email VARCHAR(255) NOT NULL COMMENT '收件人邮箱',
    recipient_name VARCHAR(128) NULL COMMENT '收件人姓名',
    subject VARCHAR(512) NOT NULL COMMENT '邮件主题',
    body TEXT NULL COMMENT '邮件正文',
    body_html TEXT NULL COMMENT 'HTML正文',
    sender_email VARCHAR(255) NOT NULL COMMENT '发件人邮箱',
    sender_name VARCHAR(128) NULL COMMENT '发件人名称',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/sending/sent/failed/delivered/opened/clicked/bounced/complained',
    sent_at DATETIME NULL COMMENT '发送时间',
    delivered_at DATETIME NULL COMMENT '送达时间',
    opened_at DATETIME NULL COMMENT '打开时间',
    clicked_at DATETIME NULL COMMENT '点击时间',
    bounced_at DATETIME NULL COMMENT '退信时间',
    bounced_reason VARCHAR(255) NULL COMMENT '退信原因',
    error_message VARCHAR(512) NULL COMMENT '错误信息',
    tracking_id VARCHAR(64) NULL COMMENT '追踪ID',
    message_id VARCHAR(255) NULL COMMENT '邮件服务器Message-ID',
    ip_address VARCHAR(64) NULL COMMENT '发送IP',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_email_sends_tenant_id (tenant_id),
    INDEX idx_email_sends_campaign_id (campaign_id),
    INDEX idx_email_sends_template_id (template_id),
    INDEX idx_email_sends_customer_id (customer_id),
    INDEX idx_email_sends_recipient_email (recipient_email),
    INDEX idx_email_sends_status (status),
    INDEX idx_email_sends_sent_at (sent_at),
    INDEX idx_email_sends_tracking_id (tracking_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邮件发送记录表';

-- ----------------------------
-- 5.5 邮件事件追踪表
-- ----------------------------
CREATE TABLE email_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '事件ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    send_id BIGINT NOT NULL COMMENT '发送记录ID',
    tracking_id VARCHAR(64) NOT NULL COMMENT '追踪ID',
    event_type VARCHAR(32) NOT NULL COMMENT '事件类型: delivered/opened/clicked/bounced/complained',
    event_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '事件时间',
    ip_address VARCHAR(64) NULL COMMENT 'IP地址',
    user_agent TEXT NULL COMMENT 'User Agent',
    link_url VARCHAR(1024) NULL COMMENT '点击链接',
    bounce_reason VARCHAR(255) NULL COMMENT '退信原因',
    complaint_type VARCHAR(64) NULL COMMENT '投诉类型',
    metadata JSON NULL COMMENT '附加数据',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_email_events_tenant_id (tenant_id),
    INDEX idx_email_events_send_id (send_id),
    INDEX idx_email_events_tracking_id (tracking_id),
    INDEX idx_email_events_event_type (event_type),
    INDEX idx_email_events_event_at (event_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='邮件事件追踪表';

-- ----------------------------
-- 5.6 短信发送记录表
-- ----------------------------
CREATE TABLE sms_sends (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '发送ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    campaign_id BIGINT NULL COMMENT '营销活动ID',
    template_id BIGINT NULL COMMENT '短信模板ID',
    customer_id BIGINT NULL COMMENT '客户ID',
    lead_id BIGINT NULL COMMENT '线索ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    recipient_phone VARCHAR(32) NOT NULL COMMENT '收件人手机',
    recipient_name VARCHAR(128) NULL COMMENT '收件人姓名',
    content TEXT NOT NULL COMMENT '短信内容',
    content_hash VARCHAR(64) NOT NULL COMMENT '内容哈希(去重)',
    status VARCHAR(32) NOT NULL DEFAULT 'pending' COMMENT '状态: pending/sending/sent/delivered/failed',
    sent_at DATETIME NULL COMMENT '发送时间',
    delivered_at DATETIME NULL COMMENT '送达时间',
    error_code VARCHAR(32) NULL COMMENT '错误码',
    error_message VARCHAR(512) NULL COMMENT '错误信息',
    provider VARCHAR(32) NULL COMMENT '短信服务商',
    provider_message_id VARCHAR(128) NULL COMMENT '服务商消息ID',
    segments INT NOT NULL DEFAULT 1 COMMENT '短信条数',
    cost DECIMAL(10,4) NULL COMMENT '发送成本',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_sms_sends_tenant_id (tenant_id),
    INDEX idx_sms_sends_campaign_id (campaign_id),
    INDEX idx_sms_sends_customer_id (customer_id),
    INDEX idx_sms_sends_recipient_phone (recipient_phone),
    INDEX idx_sms_sends_content_hash (content_hash),
    INDEX idx_sms_sends_status (status),
    INDEX idx_sms_sends_sent_at (sent_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='短信发送记录表';

-- ----------------------------
-- 5.7 营销分群表
-- ----------------------------
CREATE TABLE marketing_segments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分群ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(128) NOT NULL COMMENT '分群名称',
    code VARCHAR(64) NOT NULL COMMENT '分群编码',
    description TEXT NULL COMMENT '分群描述',
    segment_type VARCHAR(32) NOT NULL COMMENT '分群类型: static/dynamic',
    source_entity VARCHAR(32) NOT NULL COMMENT '来源实体: customer/lead/contact',
    filter_logic JSON NOT NULL COMMENT '筛选条件逻辑',
    estimated_count INT NULL COMMENT '预估人数',
    actual_count INT NULL COMMENT '实际人数',
    last_calculated_at DATETIME NULL COMMENT '最后计算时间',
    is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用: 0=否, 1=是',
    sync_to_external TINYINT NOT NULL DEFAULT 0 COMMENT '是否同步到外部: 0=否, 1=是',
    external_platform VARCHAR(64) NULL COMMENT '外部平台',
    owner_id BIGINT NOT NULL COMMENT '负责人',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_marketing_segments_tenant_id (tenant_id),
    INDEX idx_marketing_segments_code (code),
    INDEX idx_marketing_segments_segment_type (segment_type),
    INDEX idx_marketing_segments_source_entity (source_entity),
    INDEX idx_marketing_segments_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='营销分群表';

-- ----------------------------
-- 5.8 分群筛选条件表
-- ----------------------------
CREATE TABLE segment_filters (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '筛选ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    segment_id BIGINT NOT NULL COMMENT '分群ID',
    field_name VARCHAR(64) NOT NULL COMMENT '字段名称',
    field_label VARCHAR(128) NOT NULL COMMENT '字段标签',
    operator VARCHAR(32) NOT NULL COMMENT '操作符: eq/ne/gt/gte/lt/lte/contains/starts_with/ends_with/in/not_in/between/is_null/is_not_null',
    field_value TEXT NULL COMMENT '字段值',
    field_type VARCHAR(32) NOT NULL COMMENT '字段类型: text/number/date/datetime/select/boolean',
    group_logic VARCHAR(8) NOT NULL DEFAULT 'AND' COMMENT '组内逻辑: AND/OR',
    group_index INT NOT NULL DEFAULT 0 COMMENT '条件组索引',
    sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_segment_filters_tenant_id (tenant_id),
    INDEX idx_segment_filters_segment_id (segment_id),
    INDEX idx_segment_filters_group_index (group_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分群筛选条件表';

-- =============================================================================
-- 6. 客服/工单（5张表）
-- =============================================================================

-- ----------------------------
-- 6.1 工单表
-- ----------------------------
CREATE TABLE tickets (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '工单ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    ticket_no VARCHAR(64) NOT NULL COMMENT '工单编号',
    subject VARCHAR(512) NOT NULL COMMENT '工单主题',
    content TEXT NULL COMMENT '工单内容',
    customer_id BIGINT NULL COMMENT '客户ID',
    contact_id BIGINT NULL COMMENT '联系人ID',
    category VARCHAR(64) NULL COMMENT '工单类别',
    priority TINYINT NOT NULL DEFAULT 2 COMMENT '优先级: 1=紧急, 2=高, 3=中, 4=低',
    status VARCHAR(32) NOT NULL DEFAULT 'open' COMMENT '状态: open/pending/on_hold/solved/closed/cancelled',
    channel VARCHAR(32) NOT NULL COMMENT '渠道: email/phone/chat/web/social',
    satisfaction VARCHAR(32) NULL COMMENT '满意度: satisfied/neutral/dissatisfied',
    satisfaction_comment TEXT NULL COMMENT '满意度评价',
    assigned_to BIGINT NULL COMMENT '分配给',
    assigned_group_id BIGINT NULL COMMENT '分配组',
    first_response_at DATETIME NULL COMMENT '首次响应时间',
    first_response_duration INT NULL COMMENT '首次响应时长(秒)',
    resolved_at DATETIME NULL COMMENT '解决时间',
    resolve_duration INT NULL COMMENT '解决时长(秒)',
    sla_id BIGINT NULL COMMENT 'SLA ID',
    sla_breached TINYINT NOT NULL DEFAULT 0 COMMENT '是否违反SLA: 0=否, 1=是',
    tags VARCHAR(512) NULL COMMENT '标签(JSON数组)',
    attachments JSON NULL COMMENT '附件',
    source VARCHAR(64) NULL COMMENT '来源',
    source_id BIGINT NULL COMMENT '来源ID',
    campaign_id BIGINT NULL COMMENT '关联营销活动',
    order_id BIGINT NULL COMMENT '关联订单ID',
    is_locked TINYINT NOT NULL DEFAULT 0 COMMENT '是否锁定: 0=否, 1=是',
    locked_reason VARCHAR(255) NULL COMMENT '锁定原因',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    UNIQUE INDEX idx_tickets_tenant_no (tenant_id, ticket_no),
    INDEX idx_tickets_tenant_id (tenant_id),
    INDEX idx_tickets_customer_id (customer_id),
    INDEX idx_tickets_contact_id (contact_id),
    INDEX idx_tickets_assigned_to (assigned_to),
    INDEX idx_tickets_assigned_group_id (assigned_group_id),
    INDEX idx_tickets_priority (priority),
    INDEX idx_tickets_status (status),
    INDEX idx_tickets_channel (channel),
    INDEX idx_tickets_created_at (created_at),
    FULLTEXT INDEX ft_tickets_subject (subject, content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单表';

-- ----------------------------
-- 6.2 工单评论表
-- ----------------------------
CREATE TABLE ticket_comments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '评论ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    content TEXT NOT NULL COMMENT '评论内容',
    content_html TEXT NULL COMMENT 'HTML内容',
    is_internal TINYINT NOT NULL DEFAULT 0 COMMENT '是否内部评论: 0=否, 1=是',
    author_type VARCHAR(32) NOT NULL COMMENT '作者类型: customer/staff/robot',
    author_id BIGINT NOT NULL COMMENT '作者ID',
    author_name VARCHAR(128) NULL COMMENT '作者名称',
    attachments JSON NULL COMMENT '附件',
    status_to VARCHAR(32) NULL COMMENT '变更到状态',
    status_from VARCHAR(32) NULL COMMENT '变更前状态',
    parent_id BIGINT NULL COMMENT '父评论ID',
    reply_to_id BIGINT NULL COMMENT '回复评论ID',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_ticket_comments_tenant_id (tenant_id),
    INDEX idx_ticket_comments_ticket_id (ticket_id),
    INDEX idx_ticket_comments_parent_id (parent_id),
    INDEX idx_ticket_comments_author_id (author_id),
    INDEX idx_ticket_comments_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单评论表';

-- ----------------------------
-- 6.3 工单状态变更历史表
-- ----------------------------
CREATE TABLE ticket_status_history (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    status_from VARCHAR(32) NULL COMMENT '原状态',
    status_to VARCHAR(32) NOT NULL COMMENT '新状态',
    change_type VARCHAR(32) NOT NULL COMMENT '变更类型: manual/auto/system',
    operator_id BIGINT NOT NULL COMMENT '操作人',
    reason VARCHAR(255) NULL COMMENT '变更原因',
    duration_seconds INT NULL COMMENT '状态持续时长(秒)',
    changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '变更时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_ticket_status_history_tenant_id (tenant_id),
    INDEX idx_ticket_status_history_ticket_id (ticket_id),
    INDEX idx_ticket_status_history_status_to (status_to),
    INDEX idx_ticket_status_history_operator_id (operator_id),
    INDEX idx_ticket_status_history_changed_at (changed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单状态变更历史表';

-- ----------------------------
-- 6.4 工单SLA表
-- ----------------------------
CREATE TABLE ticket_sla (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT 'SLA ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    name VARCHAR(128) NOT NULL COMMENT 'SLA名称',
    code VARCHAR(64) NOT NULL COMMENT 'SLA编码',
    description VARCHAR(255) NULL COMMENT 'SLA描述',
    priority TINYINT NOT NULL COMMENT '对应优先级',
    response_time_minutes INT NOT NULL COMMENT '响应时限(分钟)',
    resolve_time_minutes INT NOT NULL COMMENT '解决时限(分钟)',
    next_escalation_minutes INT NULL COMMENT '下次升级时限(分钟)',
    escalation_user_id BIGINT NULL COMMENT '升级用户ID',
    escalation_group_id BIGINT NULL COMMENT '升级组ID',
    is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用: 0=否, 1=是',
    is_default TINYINT NOT NULL DEFAULT 0 COMMENT '是否默认: 0=否, 1=是',
    business_hours_only TINYINT NOT NULL DEFAULT 0 COMMENT '仅工作时间: 0=否, 1=是',
    holidays JSON NULL COMMENT '节假日配置',
    work_hours JSON NULL COMMENT '工作时间配置',
    deleted_at TIMESTAMP NULL COMMENT '软删除时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_by BIGINT NULL COMMENT '创建人',
    updated_by BIGINT NULL COMMENT '更新人',
    INDEX idx_ticket_sla_tenant_id (tenant_id),
    INDEX idx_ticket_sla_priority (priority),
    INDEX idx_ticket_sla_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单SLA表';

-- ----------------------------
-- 6.5 工单分配记录表
-- ----------------------------
CREATE TABLE ticket_assignments (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '分配ID',
    tenant_id BIGINT NOT NULL COMMENT '租户ID',
    ticket_id BIGINT NOT NULL COMMENT '工单ID',
    assign_type VARCHAR(32) NOT NULL COMMENT '分配方式: manual/auto/round_robin/load_balance',
    assigned_from BIGINT NULL COMMENT '分配前负责人',
    assigned_to BIGINT NOT NULL COMMENT '分配后负责人',
    assigned_group_id BIGINT NULL COMMENT '分配组',
    priority TINYINT NULL COMMENT '分配时优先级',
    reason VARCHAR(255) NULL COMMENT '分配原因',
    assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '分配时间',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    created_by BIGINT NULL COMMENT '创建人',
    INDEX idx_ticket_assignments_tenant_id (tenant_id),
    INDEX idx_ticket_assignments_ticket_id (ticket_id),
    INDEX idx_ticket_assignments_assigned_to (assigned_to),
    INDEX idx_ticket_assignments_assigned_group_id (assigned_group_id),
    INDEX idx_ticket_assignments_assign_type (assign_type),
    INDEX idx_ticket_assignments_assigned_at (assigned_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='工单分配记录表';

-- =============================================================================
-- 结束标记
-- =============================================================================

SET FOREIGN_KEY_CHECKS = 1;

-- 完成标记
-- CREATE TIME: 2026-04-12
-- TOTAL TABLES: 51
-- TOTAL INDICES: ~180+
