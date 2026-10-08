from workstation import WorkstationAbility
from sample import Sample

# 高通量XRD工作站：
# 限制
# 容器必须是离心管架
# 离心管架上的容器可为50ml试管
# 总容器数在1-10之间
# 容器没有盖子
# 容器内为悬浊液
# 溶液体积在5-30ml
def high_throughput_xrd_workstation_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] not in ["50ml_centrifuge_tube"]:
            raise Exception("离心管架上容器应为50ml试管")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-10之间")
        if sample.data['container']['subcontainer']['covered'] is not False:
            raise Exception("容器不能有盖子")
        if sample.data['container']['subcontainer']['subcontainer_phase'] != "suspension":
            raise Exception("容器内液体应为悬浊液")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] < 5 or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 30):
            raise Exception("溶液体积要在5~30ml内")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内为悬浊液（状态未改变）
def high_throughput_xrd_workstation_ability(sample: Sample):
    return sample

high_throughput_xrd_workstation = WorkstationAbility(
    name="high_throughput_xrd_workstation",
    constraints=high_throughput_xrd_workstation_constraints,
    ability=high_throughput_xrd_workstation_ability
)


def get_description():
    return {
        'name': '高通量XRD工作站',
        'noteCn': 'X 射线衍射仪主要用于分析材料的晶体结构。它通过发射 X 射线到样品上，然后测量衍射 X 射线的角度和强度。根据布拉格定律，不同的晶体结构会产生特定的衍射图案。在大学的材料科学实验室中，可用于鉴定材料中的物相，确定晶体的晶格参数、晶体缺陷等信息。对于研究新型材料的结构和性能关系，如半导体材料、陶瓷材料等，有着不可或缺的作用。该工作站主要负责材料晶体结构分析：1、高分辨率衍射：支持高分辨率的X射线衍射测量，能够解析材料的晶体结构、相变、应力、晶粒大小等信息。2、粉末衍射模式（Powder XRD）：用于晶体粉末样品的相分析、晶体结构解析。3、薄膜衍射（Thin Film XRD）：用于薄膜材料的表面结构分析，如薄膜厚度、晶体取向等。4、单晶衍射（Single Crystal XRD）：高精度的单晶结构解析。5、高角度和低角度衍射（High/Low angle XRD）：适用于多种样品的测量，提供更多角度的高精度数据。6、定量相分析（Quantitative Phase Analysis）：能够通过XRD数据对样品中的不同晶相进行定量分析，常用于材料的组成分析。7、力/应变分析通过衍射峰的位移和宽度，进行材料内部的应力和应变分析，适用于金属、陶瓷等材料。'
    }

