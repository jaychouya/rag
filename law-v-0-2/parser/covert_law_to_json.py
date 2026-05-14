

# from tmindai.dataconvert.pipeline.pipeline import MySQLInsertWriter, MySQLReader, Pipeline


# version = 0
# srcDB = "petition_src"
# dstDB = "petition"
# tableName = "dc12389"
# sql_reader = MySQLReader(db_name=srcDB, table_name=tableName, current_version=version)
# sql_writer = MySQLInsertWriter(db_name=dstDB, table_name=tableName, columns=sql_reader.get_columns(), current_version=version)
# # Choose appropriate reader and writer
# pipeline = Pipeline(sql_reader, [], sql_writer, batch_size=10)
# pipeline.run_pipeline()
import json
import os

from .doc_parser import law_to_json

INPUT_DIR = '/Users/zhangfan/work/省厅/法规/筛选后/工作制度'
SUB_DIRS = ['1.1督察工作制度', '1.3信访工作制度', '1.2审计工作制度', '1.4其他法律法规']
#OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
def convert_to_json(input_dir: str):
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory {input_dir} does not exist.")
    # if not os.path.exists(OUTPUT_DIR):
    #     os.makedirs(OUTPUT_DIR)

    error_files = []
    total_files = 0
    
    for file in os.listdir(input_dir):
        if file.endswith(".doc") or file.endswith(".docx") or file.endswith(".pdf"):
            file_path = os.path.join(input_dir, file)
            if not os.path.isfile(file_path):
                print(f"Skipping {file_path}, not a file.")
                continue
            #print(f"Processing {file_path}...")
            # Convert each file to JSON
            try:
              json_data = law_to_json(file_path)
              output_file = os.path.join(os.path.dirname(file_path), os.path.basename(file_path) + ".json")
              with open(output_file, 'w', encoding='utf-8') as f:
                  f.write(json.dumps(json_data, ensure_ascii=False, indent=4))
              total_files += 1
            except Exception as e:
              error_files.append((file_path, str(e)))

    if error_files:
        print("Errors occurred while processing the following files:")
        for file_path, error_message in error_files:
            print(f" - {file_path}: {error_message}")
    print(f"Total files processed: {total_files}, Errors: {len(error_files)}")

convert_to_json(os.path.join(INPUT_DIR, SUB_DIRS[0]))
convert_to_json(os.path.join(INPUT_DIR, SUB_DIRS[1]))
convert_to_json(os.path.join(INPUT_DIR, SUB_DIRS[2]))
convert_to_json(os.path.join(INPUT_DIR, SUB_DIRS[3]))

# ret = law_to_json('test/浙江省公安厅机关预算项目绩效管理实施细则.pdf')
# print(json.dumps(ret, ensure_ascii=False, indent=4))

