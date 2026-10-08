from workstation import WorkstationAbility
from sample import Sample
import random

# 磁力搅拌工作站
# 限制：
# 容器必须是离心管架
# 离心管架上的容器可为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-10之间
# 容器里必须为液体或悬浊液
# 不能没有液体
# 液体量不超过30ml
def magnetic_stirring_workstation_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]:
            raise Exception("离心管架上的容器应为50ml试管、聚四氟反应瓶或西林瓶")
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
def magnetic_stirring_workstation_ability(sample: Sample):
    return sample

magnetic_stirring_workstation = WorkstationAbility(
    name="magnetic_stirring_workstation",
    constraints=magnetic_stirring_workstation_constraints,
    ability=magnetic_stirring_workstation_ability
)


def get_description():
    return {
        'name': '磁力搅拌工作站',
        'noteCn': '自动液体处理工作站是一种多功能的液体处理设备。它可以进行精确的移液、分液、混合等操作，并且能够根据不同的实验需求进行灵活编程。其配备的高精度液体处理模块和智能控制系统，确保了液体处理的准确性和重复性。在药物研发、临床检验等领域，可用于高通量的样品处理，如药物筛选实验中的样品稀释、混合等操作，提高实验效率和质量。该工作站用于自动精确定量地向反应体系或分析系统添加液体，适用于小体积（1 mL）的液体进样需求，可通过程序精确控制液体进样量、速度、顺序和开关瓶盖，实现多样品或多试剂的批量处理。'
    }