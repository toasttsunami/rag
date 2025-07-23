import os
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv
load_dotenv()

class Config:
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    RETRIEVAL_K = 5

class RetrievalService:
    def __init__(self):
        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=Config.GOOGLE_API_KEY
        )
        self.vector_store = None
        self.retriever = None

    def add_documents(self, documents):
        """Add documents to vector store"""
        if self.vector_store is None:
            self.vector_store = FAISS.from_documents(documents, self.embeddings)
        else:
            self.vector_store.add_documents(documents)

        self.retriever = self.vector_store.as_retriever(
            search_kwargs={"k": Config.RETRIEVAL_K}
        )

    def retrieve_documents(self, query: str):
        """Retrieve relevant documents"""
        if not self.retriever:
            return []
        return self.retriever.invoke(query)