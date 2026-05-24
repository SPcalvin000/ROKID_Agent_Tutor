# Agent_Project/seed_milvus.py
import os
import time
import asyncio
from dotenv import load_dotenv
from openai import AsyncOpenAI

# 🌟 切换为官方最新、最高含金量的现代 MilvusClient API
from pymilvus import MilvusClient, DataType

load_dotenv()
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")

# ================= 新增：防止本地代理拦截数据库连接 =================
os.environ["NO_PROXY"] = "127.0.0.1,localhost,dashscope.aliyuncs.com"

# 1. 初始化最新的 Milvus 客户端（带自动重试鲁棒性）
print("🔌 正在尝试建立与 Docker Milvus 服务的连接...")
client_milvus = None

# 循环重试 5 次，每次间隔 5 秒，防止 Milvus 刚启动还没准备好
# 尝试使用 localhost 替代 127.0.0.1 绕开代理层的 IP 拦截
# 🎯 正确的解法：显式指定 tcp:// 前缀，彻底对齐 gRPC 端口！
# ================= 🎯 针对 Windows Docker 网络深坑的终极解法 =================
# 1. 强制清空当前 Python 进程的代理环境变量，不留一丝走错网卡的可能
# 1. 初始化最新的 Milvus 客户端（带自动重试鲁棒性）
print("🔌 正在尝试建立与 Docker Milvus 服务的连接...")
client_milvus = None

for attempt in range(1, 6):
    try:
        # 🌟 既然服务活了，直接使用官方标准的 http 协议 URI 即可完美连接！
        client_milvus = MilvusClient(uri="http://localhost:19530")
        print("🟢 成功连上 Milvus 向量引擎！")
        break
    except Exception as e:
        print(f"⏳ 连接失败原因提示: {e}")
        print(f"⏳ Milvus 服务正在初始化，等待 5 秒后进行第 {attempt}/5 次重试...")
        time.sleep(5)

if not client_milvus:
    raise RuntimeError("❌ 无法连接到 Milvus 服务，请确认 Docker 容器状态正常且已完全就绪。")


# 2. 文本向量化函数（调用通义千问通用 Embedding 模型）
async def get_embedding(text: str) -> list:
    """使用阿里云兼容接口获取文本的 1536 维向量"""
    client_llm = AsyncOpenAI(
        api_key=DASHSCOPE_API_KEY,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    response = await client_llm.embeddings.create(
        model="text-embedding-v3",
        input=text
    )
    return response.data[0].embedding


async def main():
    collection_name = "user_weakness_vector_db"

    # 3. 如果已有旧集合，先清理，防止重复插入
    if client_milvus.has_collection(collection_name):
        print(f"🗑️ 发现旧的集合 {collection_name}，正在清理...")
        client_milvus.drop_collection(collection_name)

    # 4. 🌟 使用现代 API 声明表结构与创建集合
    # 新版 Milvus 客户端支持一键构建 Schema、Index 和 Collection，极度优雅
        # 4. 🌟 使用现代 API 声明表结构与创建集合
    print(f"🏗️ 正在创建 Milvus 商业级向量集合: {collection_name}...")

        # 🎯 修复点 1：使用 MilvusClient.create_schema() 静态方法
    schema = MilvusClient.create_schema(
            description="IELTS Candidate Long-term Memory and Weakness Profile",
            auto_id=True  # 启用自动生成主键 ID
        )

        # 添加各个字段属性
    schema.add_field(field_name="id", datatype=DataType.INT64, is_primary=True)
    schema.add_field(field_name="scene_tag", datatype=DataType.VARCHAR, max_length=100)
    schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=1000)
    # 🎯 终极修复：将 OpenAI 习惯的 1536 改为阿里云通义模型实际输出的 1024
    schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=1024)

        # 5. 定义向量检索索引参数
        # 🎯 修复点 2：使用 MilvusClient.prepare_index_params() 静态方法
    index_params = MilvusClient.prepare_index_params()
    index_params.add_index(
            field_name="vector",
            metric_type="COSINE",  # 余弦相似度算法
            index_type="IVF_FLAT",  # 倒排索引标准方案
            params={"nlist": 128}
        )

        # 一键创建集合（包含 Schema 与索引绑定）
    client_milvus.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )

    # 6. 准备要塞入的“真”用户弱点数据
    raw_weakness_text = (
        "该考生英语基础较为薄弱，词汇量匮乏。历史记录显示，他极度害怕在快餐厅、"
        "麦当劳、咖啡厅等真实场景下用英语进行点餐、询问菜单和结账。请在提问时，"
        "针对性地考察这些生存口语能力。"
    )

    print("🧠 正在调用阿里云 Embedding 模型对弱点文本进行高维特征提取...")
    text_vector = await get_embedding(raw_weakness_text)

    # 7. 插入实体数据
    data = [
        {
            "scene_tag": "fast food restaurant",
            "content": raw_weakness_text,
            "vector": text_vector
        }
    ]

    print("📥 正在向 Docker Milvus 写入向量数据...")
    client_milvus.insert(collection_name=collection_name, data=data)

    print("🎉 Milvus 数据向量化灌入全部成功！长期记忆库已进入就绪状态！")


if __name__ == "__main__":
    asyncio.run(main())