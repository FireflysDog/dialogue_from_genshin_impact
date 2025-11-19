import re
import json
import os
import glob

def extract_dialogues_from_txt():
    # 定义匹配模式
    # 匹配格式: [章节名] 人名 : 对话文本
    # 要求冒号前后必须有空格，且只支持英文冒号，人名不能为空
    pattern = re.compile(r'^\[(.*?)\]\s+(.+?)\s+:\s+(.+)$')

    # 获取当前目录下所有的 narrative_data_*.txt 文件
    txt_files = ['narration/narrative_data_world.txt']
    
    all_dialogues = []

    for txt_file in txt_files:
        print(f"正在处理文件: {txt_file}")
        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            file_dialogues = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                match = pattern.match(line)
                if match:
                    source_title = match.group(1)
                    speaker = match.group(2)
                    text = match.group(3)
                    
                    dialogue_entry = {
                        "source_title": source_title,
                        "speaker": speaker,
                        "text": text
                    }
                    file_dialogues.append(dialogue_entry)
            
            print(f"  - 从 {txt_file} 提取了 {len(file_dialogues)} 条对话")
            all_dialogues.extend(file_dialogues)
            
        except Exception as e:
            print(f"处理文件 {txt_file} 时出错: {e}")

    # 导出为 JSON
    output_file = 'extraction/extracted_from_world.json'
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_dialogues, f, ensure_ascii=False, indent=4)
        print(f"\n所有提取的对话已保存至: {output_file}")
        print(f"共计提取: {len(all_dialogues)} 条")
    except Exception as e:
        print(f"保存 JSON 文件时出错: {e}")

def merge_dialogues():
    """将提取的对话合并到主对话文件中"""
    extracted_file = 'extraction/extracted_from_world.json'
    main_file = 'dialogue/dialogue_data_world.json'
    
    if not os.path.exists(extracted_file):
        print(f"未找到提取文件: {extracted_file}")
        return
        
    if not os.path.exists(main_file):
        print(f"未找到主文件: {main_file}，将直接重命名提取文件。")
        os.rename(extracted_file, main_file)
        return

    try:
        # 读取提取的对话
        with open(extracted_file, 'r', encoding='utf-8') as f:
            extracted_data = json.load(f)
            
        # 读取主对话文件
        with open(main_file, 'r', encoding='utf-8') as f:
            main_data = json.load(f)
            
        # 合并数据
        initial_count = len(main_data)
        main_data.extend(extracted_data)
        final_count = len(main_data)
        
        # 保存合并后的数据
        with open(main_file, 'w', encoding='utf-8') as f:
            json.dump(main_data, f, ensure_ascii=False, indent=4)
            
        print(f"\n合并完成！")
        print(f"主文件原数据量: {initial_count}")
        print(f"新增数据量: {len(extracted_data)}")
        print(f"合并后总数据量: {final_count}")
        print(f"数据已保存至: {main_file}")
        
    except Exception as e:
        print(f"合并文件时出错: {e}")

if __name__ == "__main__":
    #extract_dialogues_from_txt()
    merge_dialogues()
