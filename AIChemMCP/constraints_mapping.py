"""
服务器工具文件与工作站实例的constraints映射关系

这个文件定义了服务器工具文件与工作站实例文件之间的映射关系，
用于在工具执行前进行constraints验证。
"""

import os
import sys

# 添加工作站实例模块路径
workstation_instances_path = os.path.join(os.path.dirname(__file__), '..', 'AIChem-LaboratorySimulator-main', 'src')
if workstation_instances_path not in sys.path:
    sys.path.append(workstation_instances_path)

# 导入工作站实例
from workstation_instances.magnetic_stirring_workstation import magnetic_stirring_workstation
from workstation_instances.dual_station_electrochemical_workstation import dual_station_electrochemical_workstation
from workstation_instances.drying_station import drying_station
from workstation_instances.centrifuge import centrifuge
from workstation_instances.ultrasonic_cleaning_workstation import ultrasonic_cleaning_workstation
from workstation_instances.photocatalytic_workstation import photocatalytic_workstation
from workstation_instances.fluorescence_spectroscopy_workstation import fluorescence_spectroscopy_workstation
from workstation_instances.uv_spectroscopy_workstation import uv_spectroscopy_workstation
from workstation_instances.high_throughput_microplate_reader_workstation import high_throughput_microplate_reader_workstation
from workstation_instances.high_throughput_ftir_workstation import high_throughput_ftir_workstation
from workstation_instances.high_throughput_xrd_workstation import high_throughput_xrd_workstation
from workstation_instances.liquid_chromatograph import liquid_chromatograph
from workstation_instances.gas_chromatograph import gas_chromatograph
from workstation_instances.multi_channel_solid_sampler import multi_channel_solid_sampler
from workstation_instances.material_station import material_station_get_tube
# storage_workstation.py 中没有直接导出实例，我们手动创建一个
from workstation import WorkstationAbility
from workstation_instances.storage_workstation import storage_workstation_constraints, storage_workstation_ability
storage_workstation = WorkstationAbility(
    name="storage_workstation",
    constraints=storage_workstation_constraints,
    ability=storage_workstation_ability
)
from workstation_instances.storage_rack import storage_rack
from workstation_instances.centrifugal_purification_workstation import centrifugal_purification_with_wash_liquid, centrifugal_purification_without_wash_liquid
from workstation_instances.oneml_liquid_sampling_station import liquid_sampling_station
from workstation_instances.solid_injection import solid_injection
# 离心管架分液站 - 特殊处理，因为文件夹名包含中文
import importlib.util
spec_decentralization = importlib.util.spec_from_file_location(
    "decentralization",
    os.path.join(workstation_instances_path, "workstation_instances", "#U6682#U672a#U90e8#U7f72#U7684#U5de5#U4f5c#U7ad9", "decentralization.py")
)
decentralization_module = importlib.util.module_from_spec(spec_decentralization)
spec_decentralization.loader.exec_module(decentralization_module)
decentralization = decentralization_module.decentralization_constraints

# 服务器工具与工作站实例的映射
SERVER_TO_WORKSTATION_MAP = {
    # 磁力搅拌相关
    'magnetic_stirring_server_tools': magnetic_stirring_workstation,

    # 电化学相关
    'electrochemical_workstation_dual_server_tools': dual_station_electrochemical_workstation,

    # 干燥相关
    'dryer_server_tools': drying_station,

    # 离心相关
    'new_centrifugation_server_tools': centrifuge,
    'pure_server_tools': centrifugal_purification_with_wash_liquid,  # 离心纯化工作站

    # 超声清洗相关
    'ultrasonic_cleaning_server_tools': ultrasonic_cleaning_workstation,

    # 光催化相关
    'ustc_photocatalysis_server_tools': photocatalytic_workstation,

    # 光谱分析相关
    'fluorescence_spectroscopy_workstation': fluorescence_spectroscopy_workstation,
    'uv_spectroscopy_workstation': uv_spectroscopy_workstation,
    'high_throughput_microplate_reader_server_tools': high_throughput_microplate_reader_workstation,
    'high_throughput_ftir_workstation': high_throughput_ftir_workstation,
    'high_throughput_xrd_workstation': high_throughput_xrd_workstation,

    # 色谱分析相关
    'liquid_chromatograph': liquid_chromatograph,
    'gas_chromatograph': gas_chromatograph,

    # 液体处理相关
    'liquid_handling_workstation_server_tools': decentralization,  # 离心管架分液站
    'liquid_dispensing_server_tools': liquid_sampling_station,  # 1ml液体进样站
    'toLC_server_tools': liquid_chromatograph,  # 液相色谱仪
    'oneml_liquid_sampling_station': liquid_sampling_station,  # 1ml液体进样站

    # 固体处理相关
    'solid_dispensing_server_tools': solid_injection,  # 固体进样工作站
    'ustc_mul_solid_server_tools': multi_channel_solid_sampler,  # 多通道固体进样器

    # 物料和存储相关
    'starting_station_server_tools': material_station_get_tube,  # 物料站
    'storage_workstation': storage_workstation,  # 存储工作站
    'storage_rack': storage_rack,  # 存储架

    # 转移相关
    'transfer_workstation_server_tools': storage_workstation,  # 置物工作站
}

def get_workstation_for_server(server_name: str):
    """根据服务器名称获取对应的工作站实例"""
    return SERVER_TO_WORKSTATION_MAP.get(server_name)

def validate_sample_constraints(server_name: str, sample):
    """使用对应工作站的constraints验证样品"""
    workstation = get_workstation_for_server(server_name)
    if workstation and workstation.constraints:
        return workstation.constraints(sample)
    return True  # 如果没有对应的constraints，默认通过

def get_all_server_workstation_mappings():
    """获取所有服务器-工作站映射关系"""
    return SERVER_TO_WORKSTATION_MAP