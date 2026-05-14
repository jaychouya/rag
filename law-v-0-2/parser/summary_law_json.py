import json
import os

from summary import summary_law_json
from tqdm import tqdm


def summary_law_dir(input_dir: str, output_dir: str = None):
    input_dir = os.path.abspath(input_dir)
    output_dir = os.path.abspath(output_dir) if output_dir else None
    if not output_dir:
        output_dir = os.path.join(input_dir, "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    success_dir= os.path.join(output_dir, "success")
    error_dir = os.path.join(output_dir, "error")
    if not os.path.exists(success_dir):
        os.makedirs(success_dir)
    if not os.path.exists(error_dir):
        os.makedirs(error_dir)
    
    json_files = [f for f in os.listdir(input_dir) if f.endswith(".json")]
    with tqdm(total=len(json_files), desc=os.path.basename(input_dir)) as pbar:
        for json_file in json_files:
            file_path = os.path.join(input_dir, json_file)
            output_file = os.path.join(success_dir, json_file)
            if os.path.exists(output_file):
                print(f"Skipping {json_file}, already processed.")
                pbar.update(1)
                continue
            try:
                summaried_json = summary_law_json(file_path, max_llm_threads=8, batch_count=8)
                output_file = os.path.join(success_dir, json_file)
                with open(output_file, "w", encoding="utf-8") as file:
                    json.dump(summaried_json, file, ensure_ascii=False, indent=4)
            except Exception as e:
                print(f"Error processing {file_path}: {e}")
                error_file = os.path.join(error_dir, json_file)
                with open(error_file, "w", encoding="utf-8") as file:
                    file.write(str(e))
            pbar.update(1)
            
#summary_law_dir(os.path.join(INPUT_DIR, SUB_DIRS[4]))

# summary_law_json('test/公安机关维护民警执法权威工作规定.json', max_llm_threads=8, batch_count=8)

if __name__ == "__main__":
    # 读取第一个参数为输入路径
    import sys
    if len(sys.argv) < 2:
        print("Usage: python summary_law_json.py <input_dir> [output_dir]")
        sys.exit(1)
    input_dir = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    summary_law_dir(input_dir, output_dir)
    
    