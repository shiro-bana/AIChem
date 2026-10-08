from workstation import WorkstationAbility
from sample import Sample

# 双工位电化学工作站
# 限制：
# 必须是离心管架进样
# 离心管架上的容器为50ml试管
# 容器必须没有盖子
# 总容器数在1-10之间
# 容器内是混合均匀的悬浊液
# 容器内体积大于4ml
def dual_station_electrochemical_workstation_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("必须是离心管架进样")
        if sample.data['container']['subcontainer']['subcontainer_name'] != "50ml_centrifuge_tube":
            raise Exception("离心管架上的容器应为50ml试管")
        if sample.data['container']['subcontainer']['covered'] is True:
            raise Exception("容器必须没有盖子")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if sample.data['container']['subcontainer']['subcontainer_phase'] != 'suspension':
            raise Exception("容器内是混合均匀的悬浊液")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] <= 4):
            raise Exception("容器内体积应该要大于4ml")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内是悬浊液
# 容器内体积基本不变
def dual_station_electrochemical_workstation_ability(sample: Sample):
    # 混合均匀的悬浊液和悬浊液是否需要作区分？
    return sample

dual_station_electrochemical_workstation = WorkstationAbility(
    name="dual_station_electrochemical_workstation",
    constraints=dual_station_electrochemical_workstation_constraints,
    ability=dual_station_electrochemical_workstation_ability
)


def get_description():
    return {
        'name': '双工位电化学工作站',
        'noteCn': '电化学工作站是一种用于电化学实验和分析的设备。它可以提供多种电化学测试技术，如循环伏安法、计时电流法、交流阻抗法等。通过控制电极的电位或电流，测量相应的电化学参数，如电流、电位、电量等。可以用于研究电极过程动力学、电化学反应机理、材料的电化学性能等。在电池研发、腐蚀防护、传感器研究等领域有着广泛的应用，例如评估电池电极材料的性能、研究金属的腐蚀行为等。该工作站用于自动化执行电化学实验，可实现多种电化学测试，如计时电流法、循环伏安法、交流阻抗法、极化曲线等。'
    }
