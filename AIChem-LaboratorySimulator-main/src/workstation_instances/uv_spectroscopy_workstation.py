from workstation import WorkstationAbility
from sample import Sample
import random

# 紫外光谱工作站
# 必须以离心管架进样
# 离心管架上的容器可为50ml试管
# 总容器数在1-10之间
# 容器没有盖子
# 容器内为液体
# 容器内体积为8-30ml
def uv_spectroscopy_workstation_constraints(sample: Sample):
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
def uv_spectroscopy_workstation_ability(sample: Sample):
    # 减少 1-3 ml 液体(约束为容器内体积至少8ml，所以不会减少到负数)
    reduction = random.uniform(1, 3)
    sample.data['container']['subcontainer']['subcontainer_volume'] -= reduction
    return sample

uv_spectroscopy_workstation = WorkstationAbility(
    name="uv_spectroscopy_workstation",
    constraints=uv_spectroscopy_workstation_constraints,
    ability=uv_spectroscopy_workstation_ability
)


def get_description():
    return {
        'name': '紫外光谱工作站',
        'noteCn': '紫外 - 可见分光光度计利用物质对紫外和可见光的吸收特性来进行分析。不同的物质对不同波长的光有特定的吸收峰，通过测量样品在不同波长下的吸光度，可以对物质进行定性和定量分析。在化学实验中，可用于测定溶液中物质的浓度，例如分析金属离子的含量。在生物领域，能检测核酸、蛋白质等生物大分子的浓度和纯度，为生物实验提供关键的数据支持。该工作站存在三种运行模式：1、定量分析模式：用于样品浓度测定。2、透过率与吸光度测量模式：适用于各种样品的光谱测量。3、比色测量模式：适用于比色分析，特别是在药物、食品等领域的应用。'
    }
