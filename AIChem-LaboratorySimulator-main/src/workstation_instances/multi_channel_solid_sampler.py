from workstation import WorkstationAbility
from sample import Sample
import random

# 多通道固体进样器
# 限制：
# 容器为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-20之间
# 容器不能有盖子
def multi_channel_solid_sampler_constraints(sample: Sample):
    try:
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]:
            raise Exception("容器应为50ml试管、聚四氟反应瓶或西林瓶")
        # 这里的总容器数为多通道进样器的通道数， 而非离心管架的离心管数，不应与sample的(sub)container_number做关联
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 20 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-20之间")
        if sample.data['container']['subcontainer']['covered'] is True:
            raise Exception("容器不能有盖子")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内为固体或者固液混合物
# 容器内样品量会增多一些
def multi_channel_solid_sampler_ability(sample: Sample):
    # 增加 2-10ml 样品量
    increase_volume = random.randint(2, 10)
    new_volume = sample.data['container']['subcontainer']['subcontainer_volume'] + increase_volume
    sample.data['container']['subcontainer']['subcontainer_volume'] = min(new_volume, 50)
    # 设置相态为固体或固液混合物
    if sample.data['container']['subcontainer']['subcontainer_phase'] == 'liquid':
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'suspension'
    else:
        sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'
    return sample

multi_channel_solid_sampler = WorkstationAbility(
    name="multi_channel_solid_sampler",
    constraints=multi_channel_solid_sampler_constraints,
    ability=multi_channel_solid_sampler_ability
)

def get_description():
    return {
        'name': '多通道固体进样器',
        'noteCn': '多通道固体自动进样仪主要用于自动、准确地将固体样品送入分析仪器中。它具有多个通道，可以同时处理多个样品，提高了进样的效率。在化学分析中，可用于将固体粉末样品送入光谱仪、质谱仪等进行成分分析；在材料研究中，可将不同的固体材料样品依次送入测试设备，进行性能测试。通过自动化的进样过程，减少了人工操作可能带来的污染和误差，保证了分析结果的准确性。该工作站用于自动化、精确称量多种固体样品，集成了高精度电子天平与多通道样品位移系统，可实现对不同通道样品的顺序称量与自动记录。'
    }

