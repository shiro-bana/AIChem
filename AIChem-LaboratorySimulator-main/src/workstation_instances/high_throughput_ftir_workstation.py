from workstation import WorkstationAbility
from sample import Sample

# 高通量红外光谱工作站：
# 限制：
# 容器必须是离心管架
# 离心管架上的容器可为50ml试管
# 总容器数在1-10之间
# 容器没有盖子
# 容器内为悬浊液
# 溶液体积在5-30ml
def high_throughput_ftir_workstation_constaints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer'] not in ["50ml_centrifuge_tube"]:
            raise Exception("离心管架上的容器应为50ml试管")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if sample.data['container']['subcontainer']['covered'] is True:
            raise Exception("试管不能有盖子")
        if sample.data['container']['subcontainer']['subcontainer_phase'] is not "suspension":
            raise Exception("容器内应为悬浊液")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] < 5 or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 30):
            raise Exception("溶液体积应在5-30ml之间")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内为悬浊液（状态未改变）
def high_throughput_ftir_workstation_ability(sample: Sample):
    return sample

high_throughput_ftir_workstation = WorkstationAbility(
    name="high_throughput_ftir_workstation",
    constraints=high_throughput_ftir_workstation_constaints,
    ability=high_throughput_ftir_workstation_ability
)


def get_description():
    return {
        'name': '高通量红外光谱工作站',
        'noteCn': '傅里叶变换红外光谱仪通过测量物质对红外光的吸收或发射来获取其分子结构信息。不同的化学键和官能团在红外光谱中有特定的吸收峰。在化学和材料研究中，可用于鉴定有机化合物的结构，判断分子中存在的官能团，如羟基、羰基等。在高分子材料研究中，能分析聚合物的组成和结构，为材料的合成和改性提供依据，帮助研究人员深入了解材料的性质和性能。该工作站提供高分辨率、高灵敏度的红外光谱数据，精确分析样品的化学成分和分子结构。'
    }
