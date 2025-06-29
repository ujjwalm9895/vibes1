import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from sentence_transformers import SentenceTransformer
import openai

class MemoryStore:
    def __init__(self):
        self.client = chromadb.Client()
        self.embedder = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        self.collection = self.client.get_or_create_collection("conversations", embedding_function=self.embedder)

    def store(self, text):
        self.collection.add(
            documents=[text],
            ids=[str(hash(text))]
        )

    def generate_follow_ups(self, ideas):
        prompts = "\n".join([idea["text"] for idea in ideas])
        messages = [
            {"role": "system", "content": "You are a creative assistant helping generate follow-ups."},
            {"role": "user", "content": f"Based on these ideas:\n{prompts}\nWhat are 3 follow-up ideas?"}
        ]
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
        return response.choices[0].message.content.strip()
