from workstation import WorkstationAbility
from sample import Sample
import random

# 1ml液体进样站
# 限制：
# 必须是离心管架进样
# 离心管架上的容器可为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-10之间
# 容器内体积不超过30ml
# 容器内为纯液体或浑浊液或纯固体
def liquid_sampling_station_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]:
            raise Exception("离心管架上的容器应为50ml试管、聚四氟反应瓶或西林瓶")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 30):
            raise Exception("容器内体积不超过30ml")
        if sample.data['container']['subcontainer']['subcontainer_phase'] not in ['liquid', 'suspension', 'solid']:
            raise Exception("容器内应为纯液体或浑浊液或纯固体")
    except Exception as e:
        print(e)
        return False
    return True

# 1，有盖-无盖
# 输出：
# 容器没有盖子
# 容器内体积不超过30ml
# 溶液量有一定程度增加
# 2，有盖-有盖
# 容器有盖子
# 容器内体积不超过30ml
# 溶液量有一定程度增加
# 3，无盖-无盖
# 容器没有盖子
# 容器内体积不超过30ml
# 溶液量有一定程度增加
def liquid_sampling_station_ability_cover2uncover(sample: Sample):
    # 增加 1ml 液体
    if sample.data['container']['subcontainer']['covered'] is True:
        sample.data['container']['subcontainer']['covered'] = False
    new_volume = sample.data['container']['subcontainer']['subcontainer_volume'] + 1
    sample.data['container']['subcontainer']['subcontainer_volume'] = min(new_volume, 30)
    return sample

def liquid_sampling_station_ability_uncover2cover(sample: Sample):
    # 增加 1ml 液体
    if sample.data['container']['subcontainer']['covered'] is False:
        sample.data['container']['subcontainer']['covered'] = True
    new_volume = sample.data['container']['subcontainer']['subcontainer_volume'] + 1
    sample.data['container']['subcontainer']['subcontainer_volume'] = min(new_volume, 30)
    return sample

def liquid_sampling_station_ability_nochange(sample: Sample):
    # 将有盖-有盖，无盖-无盖统一处理
    # 增加 1ml 液体
    new_volume = sample.data['container']['subcontainer']['subcontainer_volume'] + 1
    sample.data['container']['subcontainer']['subcontainer_volume'] = min(new_volume, 30)
    return sample

liquid_sampling_station = WorkstationAbility(
    name="liquid_sampling_station",
    constraints=liquid_sampling_station_constraints,
    ability=liquid_sampling_station_ability_nochange
)


def get_description():
    return {
        'name': '1ml液体进样站',
        'noteCn': '自动液体处理工作站是一种多功能的液体处理设备。它可以进行精确的移液、分液、混合等操作，并且能够根据不同的实验需求进行灵活编程。其配备的高精度液体处理模块和智能控制系统，确保了液体处理的准确性和重复性。在药物研发、临床检验等领域，可用于高通量的样品处理，如药物筛选实验中的样品稀释、混合等操作，提高实验效率和质量。该工作站用于自动精确定量地向反应体系或分析系统添加液体，适用于小体积（1 mL）的液体进样需求，可通过程序精确控制液体进样量、速度、顺序和开关瓶盖，实现多样品或多试剂的批量处理。'
    }

