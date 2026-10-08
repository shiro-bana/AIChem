from workstation import WorkstationAbility
from sample import Sample
import random


def material_station_constraints(sample: Sample):
    return True

# 输出为离心管架
# 离心管架上的容器可为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-10之间
# 容器为空容器

##### 无法访问试管架上的某一个容器，只能进行简单的赋值操作 #####
def material_station_ability_get_tube(sample: Sample):
    # 取50ml离心管
    sample.data['container']['container_name'] = "rack"
    sample.data['container']['subcontainer']['subcontainer_name'] = '50ml_centrifuge_tube'
    if sample.data['container']['subcontainer']['subcontainer_number'] is None:
        sample.data['container']['subcontainer']['subcontainer_number'] = 1
        sample.data['container']['subcontainer']['subcontainer_volume'] = 0
    else:
        sample.data['container']['subcontainer']['subcontainer_number'] += 1
    return sample

def material_station_ability_get_ptfe(sample: Sample):
    # 取聚四氟反应瓶
    sample.data['container']['container_name'] = "rack"
    sample.data['container']['subcontainer']['subcontainer_name'] = 'ptfe_reaction_bottle'
    if sample.data['container']['subcontainer']['subcontainer_number'] is None:
        sample.data['container']['subcontainer']['subcontainer_number'] = 1
        sample.data['container']['subcontainer']['subcontainer_volume'] = 0
    else:
        sample.data['container']['subcontainer']['subcontainer_number'] += 1
    return sample

def material_station_ability_get_vial(sample: Sample):
    # 取西林瓶
    sample.data['container']['container_name'] = "rack"
    sample.data['container']['subcontainer']['subcontainer_name'] = 'vial'
    if sample.data['container']['subcontainer']['subcontainer_number'] is None:
        sample.data['container']['subcontainer']['subcontainer_number'] = 1
        sample.data['container']['subcontainer']['subcontainer_volume'] = 0
    else:
        sample.data['container']['subcontainer']['subcontainer_number'] += 1
    return sample

material_station_get_tube = WorkstationAbility(
    name="material_station",
    constraints=material_station_constraints,
    ability=material_station_ability_get_tube
)

material_station_get_ptfe = WorkstationAbility(
    name="material_station",
    constraints=material_station_constraints,
    ability=material_station_ability_get_ptfe
)

material_station_get_vial = WorkstationAbility(
    name="material_station",
    constraints=material_station_constraints,
    ability=material_station_ability_get_vial
)


def get_description():
    return {
        'name': '物料站',
        'noteCn': '用于放置所需反应容器的初始区域，机器人从此区域拿取反应容器开始实验。'
    }