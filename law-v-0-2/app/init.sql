CREATE DATABASE IF NOT EXISTS law;

USE law;

CREATE TABLE IF NOT EXISTS LegalCategory (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type JSON NOT NULL COMMENT '法律法规分类类型',
    name VARCHAR(100) NOT NULL COMMENT '法律法规分类名称',
    summary TEXT NOT NULL COMMENT '法律法规分类描述',
    create_time DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
);

CREATE TABLE IF NOT EXISTS LegalDocuments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(1024) NOT NULL,
    category_id INT NOT NULL COMMENT '法律法规分类ID',
    FOREIGN KEY (category_id) REFERENCES LegalCategory(id),
    summary TEXT NOT NULL COMMENT '法规摘要',
    scenarios TEXT NOT NULL COMMENT '适用场景',
    subjects TEXT NOT NULL COMMENT '适用主体',
    rule_category VARCHAR(100) NOT NULL COMMENT '社会关系性质划分
     - 民事:如合同、物权、侵权
     - 刑事:如犯罪构成、刑罚裁量
     - 行政:如行政管理、行政处罚
     - 经济:如市场监管、财税金融
     - 社会:如劳动保障、社会保障
     - 宪法及宪法相关法:如国家机构、公民基本权利
     - 诉讼与非诉讼程序法:（如民事诉讼、仲裁）',
    rule_form VARCHAR(100) NOT NULL COMMENT '律形式名称,根据法规的制定主体、效力层级及表现形式划分，可选值及解释如下，当不匹配的时候使用一个词概括，格式为 其他-xxx：
     - 法律:全国人大及其常委会制定，名称含 “法”，如《民法典》
     - 行政法规:国务院制定，名称含 “条例”“办法”，如《信访工作条例》
     - 地方性法规:地方人大制定，名称含 “省 / 市 + 条例”，如《北京市物业管理条例》
     - 部门规章:国务院部委制定，名称含 “办法”“规定”，如《公共机构节能管理办法》
     - 司法解释:最高法 / 最高检发布，名称含 “解释”“批复”，如《民法典合同编解释》
     - 操作指引类:规范性文件中以办事流程为主的指引，如《社保参保办事指南》',
    rule_content_type VARCHAR(100) NOT NULL COMMENT '法规内容性质，根据法规核心内容倾向划分，可选值及解释如下，当不匹配的时候使用一个词概括，格式为 其他-xxx
     - 惩罚性:以设定法律责任、制裁违法行为为主，如《行政处罚法》
     - 指引性:以规范办事流程、权利义务分配为主，如《企业登记管理办法》
     - 综合性:同时包含惩罚性与指引性内容，如《安全生产法》',
    tags JSON NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE COMMENT '是否启用',
    create_time DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '更新时间',
    content MEDIUMTEXT NOT NULL
);
