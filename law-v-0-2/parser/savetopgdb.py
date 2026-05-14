import asyncio
import csv
import json
import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from law_compat.pgsql import PostgreSQLHelper


class LawDataSaver:
    def __init__(self, host="localhost", port=5432, database="law", username="postgres", password=""):
        """初始化数据库连接"""
        self.pg_helper = PostgreSQLHelper(
            host=host,
            port=port,
            database=database,
            username=username,
            password=password
        )
        
    async def init_database(self):
        """初始化数据库和表结构"""
        print("正在初始化数据库...")
        
        # 1. 检查并创建数据库
        await self._create_database_if_not_exists()
        
        # 2. 创建表结构
        await self._create_tables()
        
        print("数据库初始化完成")
    
    async def _create_database_if_not_exists(self):
        """创建数据库（如果不存在）"""
        # 连接到默认的postgres数据库
        temp_helper = PostgreSQLHelper(
            host=self.pg_helper.host,
            port=self.pg_helper.port,
            database="postgres",
            username=self.pg_helper.username,
            password=self.pg_helper.password
        )
        
        try:
            await temp_helper.init_pool()
            
            # 检查数据库是否存在
            result = await temp_helper.execute_query(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                [self.pg_helper.database],
                "one"
            )
            
            if not result:
                # 创建数据库
                await temp_helper.execute_script(f"CREATE DATABASE {self.pg_helper.database}")
                print(f"数据库 '{self.pg_helper.database}' 创建成功")
            else:
                print(f"数据库 '{self.pg_helper.database}' 已存在")
                
        finally:
            await temp_helper.close_pool()
    
    async def _create_tables(self):
        """创建表结构"""
        await self.pg_helper.init_pool()
        
        # 创建LegalCategory表
        create_category_table = """
        CREATE TABLE IF NOT EXISTS LegalCategory (
            id SERIAL PRIMARY KEY,
            type TEXT NOT NULL,
            name TEXT UNIQUE NOT NULL,
            summary TEXT
        );
        """
        
        # 创建LegalDocuments表
        create_documents_table = """
        CREATE TABLE IF NOT EXISTS LegalDocuments (
            id SERIAL PRIMARY KEY,
            category_id INTEGER REFERENCES LegalCategory(id),
            summary TEXT,
            scenarios TEXT,
            subjects TEXT,
            rule_category TEXT,
            rule_form TEXT,
            rule_content_type TEXT,
            tags JSONB,
            name TEXT UNIQUE NOT NULL,
            content JSONB,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
        
        # 创建更新时间触发器
        create_trigger = """
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_legal_documents_updated_at ON LegalDocuments;
        CREATE TRIGGER update_legal_documents_updated_at
            BEFORE UPDATE ON LegalDocuments
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
        """
        
        await self.pg_helper.execute_script(create_category_table)
        await self.pg_helper.execute_script(create_documents_table)
        await self.pg_helper.execute_script(create_trigger)
        
        print("表结构创建完成")
    
    async def save_categories(self, csv_file_path):
        """保存分类数据到LegalCategory表"""
        print(f"正在保存分类数据从 {csv_file_path}...")
        
        categories = []
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                categories.append({
                    'type': row['type'],
                    'name': row['name'],
                    'summary': row['summary']
                })
        
        # 清空现有数据
        await self.pg_helper.execute_query("DELETE FROM LegalCategory")
        
        # 插入新数据
        for category in categories:
            await self.pg_helper.insert('LegalCategory', category)
        
        print(f"成功保存 {len(categories)} 个分类")
    
    async def save_laws(self, csv_file_path, parsed_laws_dir):
        """保存法律文档数据到LegalDocuments表"""
        print(f"正在保存法律文档数据从 {csv_file_path}...")
        
        # 读取分类映射
        category_map = {}
        categories = await self.pg_helper.select('LegalCategory', 'id, name')
        for cat in categories:
            category_map[cat['name']] = cat['id']
        
        # 读取law.csv
        laws = []
        with open(csv_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                laws.append({
                    'law_name': row['law_name'],
                    'category_name': row['category_name']
                })
        
        # 清空现有数据
        await self.pg_helper.execute_query("DELETE FROM LegalDocuments")
        
        # 处理每个法律文档
        success_count = 0
        error_count = 0
        
        for law in laws:
            try:
                await self._process_law_document(law, category_map, parsed_laws_dir)
                success_count += 1
            except Exception as e:
                print(f"处理法律文档 '{law['law_name']}' 时出错: {e}")
                error_count += 1
        
        print(f"成功保存 {success_count} 个法律文档，失败 {error_count} 个")
    
    async def _process_law_document(self, law, category_map, parsed_laws_dir):
        """处理单个法律文档"""
        law_name = law['law_name']
        category_name = law['category_name']
        
        # 获取category_id
        category_id = category_map.get(category_name)
        if not category_id:
            raise ValueError(f"未找到分类: {category_name}")
        
        # 查找对应的JSON文件
        json_file_path = self._find_json_file(law_name, parsed_laws_dir)
        if not json_file_path:
            raise FileNotFoundError(f"未找到法律文档的JSON文件: {law_name}")
        
        # 读取JSON文件
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 验证必需字段
        required_fields = ['summary', 'docName', 'scenarios_summary', 'subjects']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"JSON文件缺少必需字段: {field}")
        
        # 准备插入数据
        document_data = {
            'category_id': category_id,
            'summary': data['summary'],
            'scenarios': data['scenarios_summary'],  # 注意字段映射
            'subjects': data['subjects'],
            'rule_category': data.get('rule_category', ''),
            'rule_form': data.get('rule_form', ''),
            'rule_content_type': data.get('rule_content_type', ''),
            'name': data['docName'],
            'content': json.dumps(data, ensure_ascii=False),
            'tags': json.dumps([category_name, data.get('rule_category', '')], ensure_ascii=False)
        }
        
        # 检查是否已存在同名记录
        existing = await self.pg_helper.select(
            'LegalDocuments',
            'id, tags',
            'name = $1',
            [data['docName']]
        )
        
        if existing:
            # 更新现有记录
            existing_id = existing[0]['id']
            existing_tags = json.loads(existing[0]['tags']) if existing[0]['tags'] else []
            
            # 追加新的tags并去重
            new_tags = list(set(existing_tags + [category_name, data.get('rule_category', '')]))
            document_data['tags'] = json.dumps(new_tags, ensure_ascii=False)
            
            await self.pg_helper.update(
                'LegalDocuments',
                document_data,
                'id = $1',
                [existing_id]
            )
            print(f"更新现有记录: {data['docName']}")
        else:
            # 插入新记录
            await self.pg_helper.insert('LegalDocuments', document_data)
            print(f"插入新记录: {data['docName']}")
    
    def _find_json_file(self, law_name, parsed_laws_dir):
        """查找对应的JSON文件"""
        # 遍历parsed_laws目录及其子目录
        for root, dirs, files in os.walk(parsed_laws_dir):
            for file in files:
                if file.endswith('.json'):
                    # 去掉.json后缀进行比较
                    file_name_without_ext = os.path.splitext(file)[0]
                    if file_name_without_ext == law_name:
                        return os.path.join(root, file)
        return None
    
    async def close(self):
        """关闭数据库连接"""
        await self.pg_helper.close_pool()


async def main():
    """主函数"""
    # 配置数据库连接参数
    saver = LawDataSaver(
        host=os.getenv("PGDB_HOST"),
        port=os.getenv("PGDB_PORT"),
        database=os.getenv("PGDB_NAME"),
        username=os.getenv("PGDB_USER"),
        password=os.getenv("PGDB_PASS")  # 根据实际情况设置密码
    )
    
    try:
        # 初始化数据库
        await saver.init_database()
        
        # 保存分类数据
        category_csv_path = "laws/parsed_laws/category.csv"
        if os.path.exists(category_csv_path):
            await saver.save_categories(category_csv_path)
        else:
            print(f"分类CSV文件不存在: {category_csv_path}")
            return
        
        # 保存法律文档数据
        law_csv_path = "laws/parsed_laws/law.csv"
        parsed_laws_dir = "laws/parsed_laws"
        
        if os.path.exists(law_csv_path) and os.path.exists(parsed_laws_dir):
            await saver.save_laws(law_csv_path, parsed_laws_dir)
        else:
            print(f"法律文档CSV文件或解析目录不存在: {law_csv_path} 或 {parsed_laws_dir}")
            return
        
        print("数据保存完成！")
        
    except Exception as e:
        print(f"保存数据时出错: {e}")
        raise
    finally:
        await saver.close()


if __name__ == "__main__":
    asyncio.run(main())
