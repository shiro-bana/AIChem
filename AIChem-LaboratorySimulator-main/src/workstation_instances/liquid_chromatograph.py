from workstation import WorkstationAbility
from sample import Sample

# 液相色谱仪
# 限制：
# 容器必须是色谱瓶
# 总容器数在1-54之间
# 容器没有盖子
# 容器内有微量液体
def liquid_chromatograph_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "chromatography_vial":
            raise Exception("容器必须是色谱瓶")
        ###### 这里总容器数可能指代液相色谱仪的容量，可能无法用subcontainer_number指代 ######
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 54 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总容器数在1-54之间")
        if sample.data['container']['subcontainer']['covered'] is not False:
            raise Exception("容器必须没有盖子")
        if (sample.data['container']['subcontainer']['subcontainer_phase'] != 'liquid' or 
            sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] <= 0 or
            sample.data['container']['subcontainer']['subcontainer_volume'] > 5):
            raise Exception("容器内必须有微量液体")
    except Exception as e:
        print(e)
        return False
    return True

# 输出：
# 容器内为微量液体
# 体积不发生变化
def liquid_chromatograph_ability(sample: Sample):
    # 液相色谱仪不改变样品，只进行分析
    return sample

liquid_chromatograph = WorkstationAbility(
    name="liquid_chromatograph",
    constraints=liquid_chromatograph_constraints,
    ability=liquid_chromatograph_ability
)


def get_description():
    return {
        'name': '液相色谱仪',
        'noteCn': '液相色谱仪适用于分离和分析高沸点、热不稳定的化合物。它利用不同物质在固定相和流动相之间的吸附、分配等作用的差异进行分离。在生物制药行业，可用于分离和纯化蛋白质、多肽等生物大分子药物；在药物分析中，可检测药物中的有效成分和杂质含量。液相色谱仪具有分离效率高、选择性好等特点，并且可以通过选择不同的色谱柱和流动相来满足各种复杂样品的分析需求，为药物研发和质量控制提供重要的技术支持。液相色谱仪用于液相样品的组分分离、定性与定量分析，特别适用于检测反应液中的底物、产物及中间体。该模块可实现自动进样、梯度洗脱（等度洗脱）及数据分析，适用于复杂有机体系、酶催化体系、以及自动化反应后的混合样品检测。'
    }

