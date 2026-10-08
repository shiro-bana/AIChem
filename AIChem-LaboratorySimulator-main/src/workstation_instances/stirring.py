from workstation import WorkstationAbility
from sample import Sample
import random

# 磁力搅拌工作站：
# 限制：
# 离心管架
# 50ml离心管
# 离心管有1-10个
# 液体或者固液混合
# 盖子没盖住
# 必须要有样品（3ml以上）
def stirring_constraints(sample: Sample):
    try:
        if sample.data['container']['container_name'] != "rack":
            raise Exception("容器必须是离心管架")
        if sample.data['container']['subcontainer']['subcontainer_name'] != "50ml_centrifuge_tube":
            raise Exception("离心管架上的物品必须是50ml离心管")
        if (sample.data['container']['subcontainer']['subcontainer_number'] is None or
            sample.data['container']['subcontainer']['subcontainer_number'] > 10 or
            sample.data['container']['subcontainer']['subcontainer_number'] < 1):
            raise Exception("总离心管数在1-10之间")
        if sample.data['container']['subcontainer']['subcontainer_phase'] not in ['liquid', 'slurry']:
            raise Exception("离心管内里得是液体或固液混合物")
        if sample.data['container']['subcontainer']['covered'] is not False:
            raise Exception("离心管不能盖上盖子")
        if (sample.data['container']['subcontainer']['subcontainer_volume'] is None or
            sample.data['container']['subcontainer']['subcontainer_volume'] < 3 or 
            sample.data['container']['subcontainer']['subcontainer_volume'] >= 50):
            raise Exception("离心管内的液体不能少于3ml或超过50ml")
    except Exception as e:
        print(e)
        return False
    return True

# 能力：
# 搅拌（不做任何处理）
def stirring_ability(sample: Sample):
    return sample

stirring = WorkstationAbility(
    name="stirring",
    constraints=stirring_constraints,
    ability=stirring_ability
)


def get_description():
    return {
        'name': '磁力搅拌工作站',
        'noteCn': '磁力搅拌工作站通过旋转的磁盘产生的离心力和剪切力，对放置在磁盘上的容器内的液体进行搅拌。它可以实现快速、高效的搅拌效果，使溶液充分混合。该工作站通常具有可调节的搅拌速度和时间设置，能够满足不同实验的需求。在化学合成、材料制备等实验中，可用于加速化学反应、促进物质的溶解和混合等，提高实验效率和产品质量。该工作站用于对液体样品或反应体系进行均匀搅拌与混合，确保反应物充分接触与体系热质传递均一。'
    }
