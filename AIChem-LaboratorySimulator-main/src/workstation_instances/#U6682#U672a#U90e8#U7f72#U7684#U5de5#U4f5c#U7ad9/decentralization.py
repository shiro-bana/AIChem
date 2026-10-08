from workstation import WorkstationAbility
from sample import Sample
import random

# 离心管架分液站
def decentralization_constraints(sample: Sample):
    try:
        # 容器必须是离心管架
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        # 离心管架上的物品必须是50ml试管
        if sample.data['container']['subcontainer']['subcontainer_name'] != "50ml_centrifuge_tube":
            raise Exception("离心管架上的物品必须是50ml试管")
        # 总试管数在1-10之间
        if (sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
                sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总试管数在1-10之间")
        # 试管里得是液体
        if sample.data['container']['subcontainer']['subcontainer_phase'] != 'liquid':
            raise Exception("试管里得是液体")
        # 试管要有盖子
        if sample.data['container']['subcontainer']['covered'] is not True:
            raise Exception("试管要有盖子")
        # 试管内溶液不能超过30ml
        if sample.data['container']['subcontainer']['subcontainer_volume'] > 30:
            raise Exception("试管内溶液不能超过30ml")
    except Exception as e:
        print(e)
        return False
    return True


def decentralization_ability_1(sample: Sample):
    # 保留清洗液，出来是液体
    sample.data['container']['subcontainer']['subcontainer_volume'] = random.randint(5, 30)
    return sample


def decentralization_ability_2(sample: Sample):
    # 不保留清洗液，出来是固体
    sample.data['container']['subcontainer']['subcontainer_volume'] = random.randint(2, 5)
    sample.data['container']['subcontainer']['subcontainer_phase'] = 'solid'
    return sample


decentralization_with_liquid = WorkstationAbility(
    name="decentralization with liquid",
    constraints=decentralization_constraints,
    ability=decentralization_ability_1
)

decentralization_without_liquid = WorkstationAbility(
    name="decentralization without liquid",
    constraints=decentralization_constraints,
    ability=decentralization_ability_2
)


def get_description():
    return {
        'name': '离心管架分液站',
        'noteCn': '离心处理工作站利用离心力的原理，对样品进行分离和处理。它配备有不同规格的转子，可以适应不同类型和体积的样品容器。通过调节离心速度、时间等参数，能够实现对不同密度、大小的物质的分离。在生物、化学等实验中广泛应用。例如在生物样品处理中，可用于分离细胞、细胞器等；在化学实验中，可用于沉淀的分离和溶液的澄清。该工作站用于对液体样品进行自动化离心分离，分离固液体系，实现样品纯化或沉淀收集。'
    }
