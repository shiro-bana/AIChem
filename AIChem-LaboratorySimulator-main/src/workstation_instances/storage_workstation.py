from workstation import WorkstationAbility
from sample import Sample


# 置物工作站
# 容器必须是离心管架
# 离心管架上的容器可为50ml试管、聚四氟反应瓶、西林瓶
# 总容器数在1-10之间
# 输入与输出样品状态一致

def storage_workstation_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube", "ptfe_reaction_bottle", "vial"]:
            raise Exception("离心管架上的容器应为50ml试管、聚四氟反应瓶或西林瓶")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
    except Exception as e:
        print(e)
        return False
    return True

def storage_workstation_ability(sample: Sample):
    # 置物工作站不改变样品，只进行存放
    return sample


def get_description():
    return {
        'name': '置物工作站',
        'noteCn': '置物工作站为样品提供一个稳定、安静的环境，用于样品的静置和平衡。在一些实验中，样品在处理后需要一定的时间进行静置，以达到稳定的状态或使某些反应充分进行。该工作站可以精确控制环境的温度、湿度等条件，确保样品在静置过程中不受外界干扰。例如在一些化学分析实验中，样品在混合或反应后需要静置一段时间以达到均匀的状态，置物工作站能够提供适宜的条件，保证实验结果的准确性。一方面用于放置合成过程中需静置反应的反应容器，另一方面用于放置合成及测试结束后的废弃容器。'
    }
