from workstation import WorkstationAbility
from sample import Sample
import random

# 荧光光谱工作站
# 必须以离心管架进样
# 离心管架上的容器可为50ml试管
# 总容器数在1-10之间
# 容器没有盖子
# 容器内为液体
# 容器内体积为8-30ml
def fluorescence_spectroscopy_workstation_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube"]:
            raise Exception("离心管架上的容器应为50ml试管")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if sample.data['container']['subcontainer']['covered'] is True:
            raise Exception("容器必须没有盖子")
        if sample.data['container']['subcontainer']['subcontainer_phase'] != 'liquid':
            raise Exception("容器内必须为液体")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] < 8 or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 30):
            raise Exception("容器内体积必须在8-30ml之间")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内为液体
# 容器内体积小幅减少
def fluorescence_spectroscopy_workstation_ability(sample: Sample):
    # 减少 1-3 ml 液体（约束为至少8ml，不会减少至负数）
    reduction = random.uniform(1, 3)
    sample.data['container']['subcontainer']['subcontainer_volume'] -= reduction
    return sample

fluorescence_spectroscopy_workstation = WorkstationAbility(
    name="fluorescence_spectroscopy_workstation",
    constraints=fluorescence_spectroscopy_workstation_constraints,
    ability=fluorescence_spectroscopy_workstation_ability
)


def get_description():
    return {
        'name': '荧光光谱工作站',
        'noteCn': '分子荧光光谱仪是一种用于分析物质分子结构和性质的仪器。它基于物质分子吸收光能后发射出荧光的原理工作。在大学实验室的化学分析中，可用于检测和定量分析具有荧光特性的化合物，如多环芳烃、某些生物分子等。通过测量荧光的发射波长、强度和寿命等参数，可以获取分子的电子结构、化学键信息以及分子间相互作用等情况，对于研究有机化合物的结构鉴定、药物分析等方面有着重要作用。该工作站主要用于荧光信号的采集和分析。'
    }
