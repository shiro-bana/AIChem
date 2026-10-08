import yaml


class Sample:
    def __init__(self,
                 yaml_file_path: str = None,
                 yaml_dict: dict = None):
        yaml_config_file = "./sample_schema.yaml"
        self.yaml_config = yaml.safe_load(open(yaml_config_file, 'r'))

        if yaml_file_path is not None:
            with open(yaml_file_path, 'r') as f:
                self.data = yaml.safe_load(f)
        elif yaml_dict is not None:
            self.data = yaml_dict
        else:
            self.data = self.create_dummy_from_schema(self.yaml_config['sample'])

    def create_dummy_from_schema(self, schema_config):
        """
        根据一个嵌套的 "schema" 字典，递归地生成一个所有叶子节点
        值都为 None 的 "dummy" 字典。

        它通过检查字典中是否包含 'type' 键来判断一个节点是否为“叶子节点”。
        """
        dummy_data = {}

        # 遍历当前层级的所有键值对
        for key, value in schema_config.items():

            # 检查值是否为字典
            if isinstance(value, dict):
                # --- 这是核心逻辑 ---
                # 如果这个字典里有 'type' 键,
                # 说明它是一个属性定义 (叶子节点)，我们将其值设为 None。
                if 'type' in value:
                    dummy_data[key] = None
                else:
                    # 如果没有 'type' 键，说明它是一个嵌套对象 (分支节点)，
                    # 我们需要递归进入更深一层。
                    dummy_data[key] = self.create_dummy_from_schema(value)
            else:
                # 如果 value 不是字典 (例如, 顶级键的值就是个字符串或数字)，
                # 也将其设为 None。
                dummy_data[key] = None

        return dummy_data