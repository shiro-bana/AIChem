from workstation import WorkstationAbility
from sample import Sample

# 高通量酶标仪工作站：
# 限制：
# 容器必须是24或者48或者96孔板
# 总容器数在1-24，1-48或1-96之间
# 容器内为微量液体
def high_throughput_microplate_reader_workstation_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] not in ["24_hole_plate", "48_hole_plate", "96_hole_plate"]:
            raise Exception("容器必须是24或者48或者96孔板")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("孔板总容器数不能小于1")
        if (sample.data['container']['container_name'] == "24_hole_plate" and
            sample.data['container']['subcontainer']['subcontainer_number'] > 24):
                raise Exception("24孔板总容器数在1-24之间")
        elif (sample.data['container']['container_name'] == "48_hole_plate" and
                sample.data['container']['subcontainer']['subcontainer_number'] > 48):
            raise Exception("48孔板总容器数在1-48之间")
        elif (sample.data['container']['container_name'] == "96_hole_plate" and
                sample.data['container']['subcontainer']['subcontainer_number'] > 96):
            raise Exception("96孔板总容器数在1-96之间")
        # 是否指代纯液体？悬浊液是否允许？
        if sample.data['container']['subcontainer']['subcontainer_phase'] not in ['liquid']:
            raise Exception("容器内应为液体")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] <= 0 or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 2):
            raise Exception("容器内液体容量应为微量")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内为微量液体
# 体积不发生变化
def high_throughput_microplate_reader_workstation_ability(sample: Sample):

    return sample

high_throughput_microplate_reader_workstation = WorkstationAbility(
    name="high_throughput_microplate_reader_workstation",
    constraints=high_throughput_microplate_reader_workstation_constraints,
    ability=high_throughput_microplate_reader_workstation_ability
)


def get_description():
    return {
        'name': '高通量酶标仪工作站',
        'noteCn': 'SpectraMax iD3 是一款高性能、多功能的酶标仪，由Molecular Devices公司推出，广泛应用于生命科学、药物筛选、临床检测以及分子生物学等领域。它结合了多种先进技术，提供卓越的分析精度和灵活性，适合高通量、高效率的实验需求。该工作站负责高通量多领域数据检测收集：1、吸光度（Absorbance）测量：可以精确测量从200到1000 nm的紫外至可见光范围内的样本吸光度，适用于ELISA、酶活性分析、细胞存活性检测等实验。2、荧光（Fluorescence）测量：能够进行单通道或多通道的荧光测量，用于荧光标记、定量分析等。3、荧光共振能量转移（FRET）：用于监测分子间的能量转移反应，适合生命科学研究中的信号传递、分子互动等实验。4、化学发光（Chemiluminescence）测量：适合检测化学发光反应，常用于免疫学和细胞生物学领域。5、光谱扫描功能：用户可以选择在不同的波长范围内进行扫描，获取光谱数据。6、微孔板（Microplate）测量：支持96孔、384孔等微孔板的高通量测量，广泛应用于高效筛选实验。'
    }