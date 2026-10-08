from workstation import WorkstationAbility
from sample import Sample

# 烘干机
# 限制：
# 容器必须是离心管架
# 离心管架上的容器可为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-10之间
# 容器里为纯液体或悬浊液或纯固体带有微量液体
# 容器内体积不超过30ml
def drying_station_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]:
            raise Exception("离心管架上的容器应为50ml试管、聚四氟反应瓶或西林瓶")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if sample.data['container']['subcontainer']['subcontainer_phase'] not in ['liquid', 'suspension', 'solid_with_tiny_liquid']:
            raise Exception("容器里为纯液体或悬浊液或纯固体带有微量液体")
        if sample.data['container']['subcontainer']['subcontainer_volume'] > 30:
            raise Exception("容器内体积不超过30ml")
    except Exception as e:
        print(e)
        return False
    return True

# 1，容器有盖子
# 输出：
# 容器内为纯液体或悬浊液
# 容器内体积不会减少太多
# 2，容器没有盖子
# 输出：
# 容器内为纯固体
def drying_station_ability(sample: Sample):
    # 有盖子，烘干后仍为液体或悬浊液，体积减少
    if sample.data['container']['subcontainer']['covered'] is True:
        new_volume = sample.data['container']['subcontainer']['subcontainer_volume'] * 0.8
        sample.data['container']['subcontainer']['subcontainer_volume'] = max(new_volume, 1)
    # 没有盖子，烘干后变为纯固体
    elif sample.data['container']['subcontainer']['covered'] is False:
        # 根据液体量决定剩余量  
        if sample.data['container']['subcontainer']['subcontainer_phase'] == 'liquid':
            sample.data['container']['subcontainer']['subcontainer_volume'] *= 0.3
        elif sample.data['container']['subcontainer']['subcontainer_phase'] == 'suspension':
            sample.data['container']['subcontainer']['subcontainer_volume'] *= 0.5
        elif sample.data['container']['subcontainer']['subcontainer_phase'] == 'solid_with_tiny_liquid':
            sample.data['container']['subcontainer']['subcontainer_volume'] *= 0.9
        # 没有盖子最后变为纯固体
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'
        
    return sample

drying_station = WorkstationAbility(
    name="drying_station",
    constraints=drying_station_constraints,
    ability=drying_station_ability
)


def get_description():
    return {
        'name': '烘干机',
        'noteCn': '通过电加热元件产生热量，利用风机使箱内空气循环流动，从而实现对物品的干燥处理。其工作原理是让热空气在箱内不断循环，均匀地传递热量给被干燥的物体，加快水分的蒸发。在大学实验室中，它常用于干燥玻璃仪器、烘干实验样品等。例如，对于刚清洗完的玻璃器皿，放入干燥箱后能快速去除残留水分，防止因水分残留影响后续实验；对于一些需要干燥保存的实验样品，也能通过它达到合适的干燥效果。该工作站用于自动化对样品、固体材料进行干燥处理，保证实验样品在反应前或反应后达到所需水分或溶剂含量。'
    }
