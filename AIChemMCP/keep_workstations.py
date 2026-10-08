#!/usr/bin/env python3
"""
保留用户指定的工作站文件
根据用户要求保留以下工作站及其对应的文件：
"""

# 需要保留的工作站文件列表
keep_workstations = [
    # 离心管架分液站
    "liquid_handling_workstation_server_v2.py",
    "liquid_handling_workstation_server_tools_v2.py",

    # 液相色谱仪
    "toLC_server_v2.py",
    "toLC_server_tools_v2.py",

    # 固体进样站
    "solid_dispensing_server_v2.py",
    "solid_dispensing_server_tools_v2.py",

    # 高通量酶标仪工作站
    "microplate_reader_server_v2.py",
    "microplate_reader_server_tools_v2.py",

    # 高通量XRD工作站
    "high_flux_xrd_workstation_server_v2.py",
    "high_flux_xrd_workstation_server_tools_v2.py",

    # 物料站
    "starting_station_server_v2.py",
    "starting_station_server_tools_v2.py",

    # 多通道固体进样器
    "ustc_mul_solid_server_v2.py",
    "ustc_mul_solid_server_tools_v2.py",

    # 离心机
    "new_centrifugation_server_v2.py",
    "new_centrifugation_server_tools_v2.py",

    # 光催化工作站
    "ustc_photocatalysis_server_v2.py",
    "ustc_photocatalysis_server_tools_v2.py",

    # 双工位电化学工作站
    "ElectrochemicalWorkstation_(including_high_speed_camera)_server_v2.py",
    "ElectrochemicalWorkstation_(including_high_speed_camera)_server_tools_v2.py",

    # 磁力搅拌工作站
    "magnetic_stirring_server_v2.py",
    "magnetic_stirring_server_tools_v2.py",

    # 离心纯化工作站
    "pure_server_v2.py",
    "pure_server_tools_v2.py",

    # 置物工作站
    "transfer_workstation_server_v2.py",
    "transfer_workstation_server_tools_v2.py",

    # 烘干机
    "dryer_server_v2.py",
    "dryer_server_tools_v2.py",

    # 超声清洗工作站
    "ultrasonic_cleaning_server_v2.py",
    "ultrasonic_cleaning_server_tools_v2.py",

    # 高通量红外光谱工作站
    "high_flux_ir_workstation_server_v2.py",
    "high_flux_ir_workstation_server_tools_v2.py",

    # 1ml液体进样站
    "liquid_dispensing_server_v2.py",
    "liquid_dispensing_server_tools_v2.py",
]

# 备注：紫外光谱工作站和气相色谱仪在现有文件中没有找到直接匹配
# 可能需要进一步确认是否有其他文件名对应的实现