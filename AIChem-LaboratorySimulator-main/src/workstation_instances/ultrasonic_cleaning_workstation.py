from workstation import WorkstationAbility
from sample import Sample
import random

# 超声清洗工作站
# 限制：
# 容器必须是离心管架
# 离心管架上的容器可为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-10之间
# 容器里必须为液体或悬浊液
# 不能没有液体
# 液体量不超过30ml
def ultrasonic_cleaning_constraints(sample: Sample): 
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]:
            raise Exception("离心管架上的物品必须是50ml试管、聚四氟反应瓶、西林瓶")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if sample.data['container']['subcontainer']['subcontainer_phase'] not in ['liquid', 'suspension']:
            raise Exception("容器里必须为液体或悬浊液")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] <= 0):
            raise Exception("不能没有液体")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 30):
            raise Exception("液体量不超过30ml")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 分散混合均匀的悬浊液或者液体
# 液体量不发生变化
def ultrasonic_cleaning_ability(sample: Sample):
    # 超声清洗不改变体积和相态，只是混合均匀
    return sample

ultrasonic_cleaning_workstation = WorkstationAbility(
    name="ultrasonic_cleaning_workstation",
    constraints=ultrasonic_cleaning_constraints,
    ability=ultrasonic_cleaning_ability
)

def get_description():
    return {
        'name': '超声清洗工作站',
        'noteCn': '该工作站用于对样品进行超声处理，通过高频声波在液体中产生空化效应，实现物质的分散、混合、促进反应或清洗等功能。'
    }
