# rag_database.py
import os
import json
import numpy as np
from sentence_transformers import SentenceTransformer, util
from datetime import datetime


class RAGDatabase:
    def __init__(self, db_path="rag_database.json", model_name="all-MiniLM-L6-v2"):
        """
        初始化RAG数据库
        """
        self.db_path = db_path
        self.model = SentenceTransformer(model_name)
        self.data = self._load_database()

        # 工作站短名称到完整名称的映射表
        self.name_mapping = {
            "物料拿取": "物料站",
            "固体进样": "固体进样站",
            "液体加样": "1ml液体进样站",
            "液体进样站": "1ml液体进样站",
            "磁力搅拌": "磁力搅拌工作站",
            "离心纯化": "离心纯化工作站",
            "烘干": "烘干机",
            "容器中转": "置物工作站",
            "物料回收": "置物工作站",
            "紫外": "紫外光谱工作站",
            "荧光": "荧光光谱工作站",
            "红外": "高通量红外光谱工作站",
            "XRD": "高通量XRD工作站",
            "酶标仪": "高通量酶标仪工作站",
            "气相色谱": "气相色谱仪",
            "液相色谱": "液相色谱仪",
            "电化学": "双工位电化学工作站",
            "光催化": "光催化工作站",
            "超声清洗": "超声清洗工作站",
            "离心": "离心机",
        }

    def normalize_workstation_name(self, short_name: str) -> str:
        """
        将短名称映射到完整的工作站名称

        Args:
            short_name: 短名称（如"离心纯化"）

        Returns:
            str: 完整名称（如"离心纯化工作站"），如果找不到映射则返回原名称
        """
        # 精确匹配
        if short_name in self.name_mapping:
            return self.name_mapping[short_name]

        # 部分匹配（例如"离心纯化"可能包含"纯化"）
        for key, value in self.name_mapping.items():
            if key in short_name or short_name in key:
                return value

        # 如果找不到映射，返回原名称
        return short_name

    def _load_database(self):
        """加载现有的数据库文件"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载数据库失败: {e}")
                return {"entries": []}
        else:
            return {"entries": []}

    def _save_database(self):
        """保存数据库到文件"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存数据库失败: {e}")
            return False

    def add_entry(self, question, workflow, metadata=None):
        """
        添加新的条目到数据库
        """
        if not question or not workflow:
            print("问题和工作流程不能为空")
            return False

        # 生成问题的嵌入向量
        question_embedding = self.model.encode(question).tolist()

        # 生成工作流程的嵌入向量
        workflow_str = json.dumps(workflow, ensure_ascii=False)
        workflow_embedding = self.model.encode(workflow_str).tolist()

        entry = {
            "id": len(self.data["entries"]) + 1,
            "question": question,
            "workflow": workflow,
            "question_embedding": question_embedding,
            "workflow_embedding": workflow_embedding,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }

        self.data["entries"].append(entry)
        return self._save_database()

    def find_similar(self, query, top_k=4, search_field="question"):
        """
        查找与查询最相似的条目
        """
        if not self.data["entries"]:
            return []

        # 生成查询的嵌入向量
        query_embedding = self.model.encode(query)

        # 准备所有条目的嵌入向量
        entry_embeddings = []
        entries = []

        for entry in self.data["entries"]:
            # ❗ 跳过与 user_goal 完全相同的问题
            if entry["question"].strip() == query.strip():
                continue
            
            if search_field == "question":
                question_embedding = self.model.encode(entry["question"]).tolist()
                embedding = np.array(question_embedding)
            entry_embeddings.append(embedding)
            entries.append(entry)

        if not entry_embeddings:
            return []

        # 计算余弦相似度
        entry_embeddings = np.array(entry_embeddings)
        query_embedding = query_embedding.astype(np.float32)
        entry_embeddings = entry_embeddings.astype(np.float32)
        similarities = util.cos_sim(query_embedding, entry_embeddings)[0]

        # 排序并获取top-k结果
        sorted_indices = np.argsort(similarities.numpy())[::-1]
        top_indices = sorted_indices[:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "entry": entries[idx],
                "similarity_score": float(similarities[idx])
            })

        return results

    def get_relevant_context(self, query, top_k=3, use_normalized_names=True):
        """
        获取与查询相关的上下文信息

        Args:
            query: 查询文本
            top_k: 返回的相似条目数量
            use_normalized_names: 是否将短名称转换为完整名称（默认True）
        """
        similar_entries = self.find_similar(query, top_k)

        if not similar_entries:
            return "没有找到相关的历史记录。"

        context = "以下是相关的历史问题和解决方案：\n\n"
        for i, result in enumerate(similar_entries, 1):
            entry = result["entry"]
            context += f"{i}. 问题: {entry['question']}\n"
            context += f"   相似度: {result['similarity_score']:.3f}\n"
            context += "   解决方案:\n"

            for j, step in enumerate(entry['workflow'], 1):
                method = step['method']
                # 如果启用名称规范化，将短名称转换为完整名称
                if use_normalized_names:
                    normalized_method = self.normalize_workstation_name(method)
                    if normalized_method != method:
                        # 添加映射说明，帮助LLM理解
                        context += f"     {j}. {normalized_method} [原名称: {method}]\n"
                    else:
                        context += f"     {j}. {method}\n"
                else:
                    context += f"     {j}. {method}\n"

            context += "\n"

        return context

    def get_entry_count(self):
        """获取数据库中的条目数量"""
        return len(self.data["entries"])

    def clear_database(self):
        """清空数据库"""
        self.data["entries"] = []
        return self._save_database()