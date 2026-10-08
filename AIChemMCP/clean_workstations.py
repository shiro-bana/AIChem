#!/usr/bin/env python3
"""
清理不需要的工作站文件
"""

import os
import shutil
from pathlib import Path

# 需要保留的工作站文件列表
keep_workstations = {
    "liquid_handling_workstation_server_v2.py",
    "liquid_handling_workstation_server_tools_v2.py",
    "toLC_server_v2.py",
    "toLC_server_tools_v2.py",
    "solid_dispensing_server_v2.py",
    "solid_dispensing_server_tools_v2.py",
    "microplate_reader_server_v2.py",
    "microplate_reader_server_tools_v2.py",
    "high_flux_xrd_workstation_server_v2.py",
    "high_flux_xrd_workstation_server_tools_v2.py",
    "starting_station_server_v2.py",
    "starting_station_server_tools_v2.py",
    "ustc_mul_solid_server_v2.py",
    "ustc_mul_solid_server_tools_v2.py",
    "new_centrifugation_server_v2.py",
    "new_centrifugation_server_tools_v2.py",
    "ustc_photocatalysis_server_v2.py",
    "ustc_photocatalysis_server_tools_v2.py",
    "ElectrochemicalWorkstation_(including_high_speed_camera)_server_v2.py",
    "ElectrochemicalWorkstation_(including_high_speed_camera)_server_tools_v2.py",
    "magnetic_stirring_server_v2.py",
    "magnetic_stirring_server_tools_v2.py",
    "pure_server_v2.py",
    "pure_server_tools_v2.py",
    "transfer_workstation_server_v2.py",
    "transfer_workstation_server_tools_v2.py",
    "dryer_server_v2.py",
    "dryer_server_tools_v2.py",
    "ultrasonic_cleaning_server_v2.py",
    "ultrasonic_cleaning_server_tools_v2.py",
    "high_flux_ir_workstation_server_v2.py",
    "high_flux_ir_workstation_server_tools_v2.py",
    "liquid_dispensing_server_v2.py",
    "liquid_dispensing_server_tools_v2.py",
}

def clean_workstations():
    servers_dir = Path("/opt/data/private/src/AIChemMCP/servers_and_tools")

    if not servers_dir.exists():
        print(f"目录 {servers_dir} 不存在")
        return

    # 创建备份目录
    backup_dir = servers_dir.parent / "servers_and_tools_backup"
    backup_dir.mkdir(exist_ok=True)

    print("开始清理不需要的工作站文件...")
    print(f"备份目录: {backup_dir}")

    # 先备份所有文件
    print("\n备份所有文件...")
    shutil.copytree(servers_dir, backup_dir / "original", dirs_exist_ok=True)

    # 遍历所有文件，删除不需要保留的
    deleted_files = []
    kept_files = []

    for file_path in servers_dir.glob("*.py"):
        if file_path.name in keep_workstations:
            kept_files.append(file_path.name)
        else:
            # 备份到deleted子目录
            deleted_backup_dir = backup_dir / "deleted"
            deleted_backup_dir.mkdir(exist_ok=True)
            shutil.copy2(file_path, deleted_backup_dir / file_path.name)

            # 删除原文件
            file_path.unlink()
            deleted_files.append(file_path.name)

    print(f"\n清理完成!")
    print(f"保留的文件数量: {len(kept_files)}")
    print(f"删除的文件数量: {len(deleted_files)}")

    if deleted_files:
        print(f"\n删除的文件:")
        for f in sorted(deleted_files):
            print(f"  - {f}")

    if kept_files:
        print(f"\n保留的文件:")
        for f in sorted(kept_files):
            print(f"  - {f}")

    print(f"\n所有删除的文件已备份到: {backup_dir / 'deleted'}")

if __name__ == "__main__":
    clean_workstations()