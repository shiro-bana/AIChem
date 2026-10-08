from workstation import WorkstationAbility
from sample import Sample
import random

# 固体进样站：
# 限制：
# 容器必须是50ml离心管
# 离心管没有盖子
# 没放满
def solid_injection_constraints(sample: Sample):
    try:
        # 容器必须是50ml离心管
        if sample.data['container']['container_name'] != "50ml_centrifuge_tube":
            raise Exception("容器必须是50ml离心管")
        # 离心管没有盖子
        if sample.data['container']['covered'] is not False:
            raise Exception("离心管要有盖子")
        # 进样前为空或状态为固体
        if sample.data['container']['container_volume'] != 0 and sample.data['container']['container_phase'] != 'solid':
            raise Exception("离心管里必须为空或固体")
        # 没放满
        if sample.data['container']['container_volume'] >= 50:
            raise Exception("离心管内的固体不能超过50ml离心管的容量")
    except Exception as e:
        print(e)
        return False
    return True

# 能力：
# 离心管出来是固体
# 比原来的容量高一点
def solid_injection_ability(sample: Sample):
    # 离心管出来是固体
    # sample.data['phase'] = 'solid'
    sample.data['container']['container_phase'] = 'solid'
    # 比原来的容量高一点
    new_volume = sample.data['container']['container_volume'] + random.randint(1, 5)
    # 不能超过50ml容量
    sample.data['container']['container_volume'] = min(new_volume, 50)
    return sample

solid_injection = WorkstationAbility(
    name="solid_injection",
    constraints=solid_injection_constraints,
    ability=solid_injection_ability
)


def get_description():
    return {
        'name': '固体进样站',
        'noteCn': '固体自动进样工作站用于自动向容器中加入固体样品。它能够准确地称量和加入一定量的固体样品，避免了人工操作可能带来的误差和污染。该工作站通常配备有高精度的称量装置和加样系统，可以按照预设的程序将固体样品准确地加入目标容器，可提高固体样品称量的效率和准确性。该工作站用于自动化将固体样品（粉末、颗粒、晶体等）精确定量地加入反应体系中，为单通道固体进样器。'
    }
