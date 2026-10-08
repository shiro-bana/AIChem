import os
import re
import ast
import shutil
from pathlib import Path

def extract_name_from_py_file(file_path):
    """从 Python 文件中提取 get_description() 函数的 name 值"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 使用 AST 安全地解析 Python 代码
        tree = ast.parse(content)
        
        # 查找 get_description 函数
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'get_description':
                # 查找 return 语句
                for subnode in ast.walk(node):
                    if isinstance(subnode, ast.Return):
                        # 尝试从返回的字典中提取 'name'
                        if isinstance(subnode.value, ast.Dict):
                            keys = [ast.unparse(key) if hasattr(ast, 'unparse') else 
                                   (key.s if isinstance(key, ast.Str) else '') 
                                   for key in subnode.value.keys]
                            values = subnode.value.values
                            
                            for i, key in enumerate(keys):
                                if key.strip("'\"") == 'name':
                                    if i < len(values):
                                        if isinstance(values[i], ast.Constant):
                                            return values[i].value
                                        elif isinstance(values[i], ast.Str):
                                            return values[i].s
        return None
    except:
        return None

def extract_names_from_src_files(src_dir):
    """从源目录提取所有 name 值"""
    valid_names = set()
    
    if not os.path.exists(src_dir):
        print(f"错误: 源目录不存在: {src_dir}")
        return valid_names
    
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                name = extract_name_from_py_file(file_path)
                if name:
                    valid_names.add(name)
                    print(f"   找到: {name} (来自: {file})")
    
    return valid_names

def file_should_be_kept(file_path, valid_names):
    """判断文件是否应该被保留"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查1: 文件是否有 get_description() 函数且name在valid_names中
        name_from_func = extract_name_from_py_file(file_path)
        if name_from_func and name_from_func in valid_names:
            return True, f"函数匹配: {name_from_func}"
        
        # 检查2: 文件内容中是否包含任意一个valid_name（作为独立字符串或值）
        # 使用正则表达式匹配，确保匹配到的是完整的name值
        for name in valid_names:
            # 匹配多种可能的格式：
            # 1. 作为字符串值: "烘干机" 或 '烘干机'
            # 2. 作为字典值: 'name': '烘干机' 或 "name": "烘干机"
            # 3. 作为变量值: displayName = "烘干机"
            # 4. 其他常见格式
            
            # 创建正则表达式模式
            patterns = [
                rf"['\"]{re.escape(name)}['\"]",  # 单引号或双引号包围
                rf"name['\"]?\s*:\s*['\"]{re.escape(name)}['\"]",  # JSON格式的name
                rf"displayName['\"]?\s*:\s*['\"]{re.escape(name)}['\"]",  # displayName
                rf"['\"]displayName['\"]\s*:\s*['\"]{re.escape(name)}['\"]",  # JSON格式的displayName
                rf"workstation['\"]?\s*:\s*['\"]{re.escape(name)}['\"]",  # workstation字段
            ]
            
            for pattern in patterns:
                if re.search(pattern, content):
                    return True, f"内容匹配[{pattern[:20]}...]: {name}"
            
            # 简单的字符串检查作为后备
            if name in content:
                return True, f"简单匹配: {name}"
        
        return False, "未找到匹配的name"
    except Exception as e:
        return False, f"检查出错: {e}"

def backup_directory(directory):
    """备份目录"""
    backup_path = f"{directory}_backup"
    if os.path.exists(directory):
        print(f"正在备份目录到: {backup_path}")
        if os.path.exists(backup_path):
            import time
            backup_path = f"{backup_path}_{int(time.time())}"
        shutil.copytree(directory, backup_path)
        return backup_path
    return None

def main():
    # 源目录 - 从中提取 name 值
    src_dir = "/opt/data/private/src/AIChem-LaboratorySimulator-main/src/workstation_instances"
    # 目标目录 - 需要清理的目录
    target_dir = "/opt/data/private/src/AIChemMCP/servers_and_tools"
    
    print("=" * 60)
    print("文件清理脚本")
    print("=" * 60)
    
    # 步骤1: 备份目标目录
    print("\n1. 备份目标目录...")
    backup_path = backup_directory(target_dir)
    if backup_path:
        print(f"   备份已创建: {backup_path}")
    
    # 步骤2: 从源目录提取所有有效的 name 值
    print("\n2. 从源目录提取 name 值...")
    valid_names = extract_names_from_src_files(src_dir)
    
    print(f"   共找到 {len(valid_names)} 个唯一的 name 值: {', '.join(valid_names)}")
    
    if not valid_names:
        print("警告: 没有找到任何有效的 name 值!")
        print("请检查源目录中的文件格式是否正确。")
        return
    
    # 步骤3: 清理目标目录
    print("\n3. 扫描目标目录...")
    files_to_keep = []
    files_to_delete = []
    
    if not os.path.exists(target_dir):
        print(f"错误: 目标目录不存在: {target_dir}")
        return
    
    # 首先扫描所有文件
    for root, dirs, files in os.walk(target_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                should_keep, reason = file_should_be_kept(file_path, valid_names)
                
                if should_keep:
                    files_to_keep.append(file_path)
                    print(f"   保留[{reason}]: {file}")
                else:
                    files_to_delete.append(file_path)
    
    # 显示统计信息
    print(f"\n统计信息:")
    print(f"   保留文件: {len(files_to_keep)} 个")
    for file in files_to_keep:
        print(f"     - {os.path.basename(file)}")
    print(f"   删除文件: {len(files_to_delete)} 个")
    
    if files_to_delete:
        print(f"\n将要删除的文件:")
        for file in files_to_delete:
            print(f"   {os.path.basename(file)}")
        
        # 确认删除
        confirm = input(f"\n确认删除以上 {len(files_to_delete)} 个文件? (输入 'yes' 继续): ")
        
        if confirm.lower() == 'yes':
            deleted_count = 0
            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"   已删除: {os.path.basename(file_path)}")
                except Exception as e:
                    print(f"   删除失败 {os.path.basename(file_path)}: {e}")
            
            print(f"\n删除完成! 共删除 {deleted_count} 个文件")
            
            # 删除空目录
            for root, dirs, files in os.walk(target_dir, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                            print(f"   删除空目录: {dir_path}")
                    except:
                        pass
        else:
            print("操作已取消")
    else:
        print("没有需要删除的文件")

if __name__ == "__main__":
    main()