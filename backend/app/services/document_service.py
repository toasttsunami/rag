from typing import List
from itertools import chain
from langchain_community.document_loaders import WebBaseLoader, PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

class Config:
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 50

class DocumentService:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            chunk_size=Config.CHUNK_SIZE,
            chunk_overlap=Config.CHUNK_OVERLAP
        )

    def load_documents(self, web_urls: List[str], local_files: List[str]):
        """Load documents from web URLs and local files"""
        docs = []

        if web_urls:
            web_docs = [WebBaseLoader(url).load() for url in web_urls]
            docs.extend(web_docs)

        if local_files:
            pdf_docs = [PyPDFLoader(file).load() for file in local_files]
            docs.extend(pdf_docs)

        return list(chain.from_iterable(docs))

    def split_documents(self, documents):
        """Split documents into chunks"""
        return self.text_splitter.split_documents(documents)