import os
from typing import List
from operator import itemgetter
from langchain import hub
from langchain_core.documents import Document
from langgraph.graph import START, StateGraph, END
from typing_extensions import TypedDict
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.tools.tavily_search import TavilySearchResults
from app.models import GradeDocuments, GraphState
from app.services.retrieval_service import RetrievalService

class Config:
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    TAVILY_API_KEY = os.environ.get('TAVILY_API_KEY')

class RAGService:
    def __init__(self, retrieval_service: RetrievalService):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-pro", google_api_key=Config.GOOGLE_API_KEY
        )
        self.retrieval_service = retrieval_service
        self.web_search = TavilySearchResults(
            max_results=3,
            search_depth="advanced",
            max_tokens=10000,
            tavily_api_key=Config.TAVILY_API_KEY,
        )

        self._setup_chains()
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        # Add nodes
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("grade_documents", self._grade_documents)
        workflow.add_node("rewrite_query", self._rewrite_query)
        workflow.add_node("web_search", self._web_search)
        workflow.add_node("generate_answer", self._generate_answer)

        # Set entry point
        workflow.set_entry_point("retrieve")

        # Add edges
        workflow.add_edge("retrieve", "grade_documents")
        workflow.add_conditional_edges(
            "grade_documents",
            self._decide_to_generate,
            {"rewrite_query": "rewrite_query", "generate_answer": "generate_answer"}
        )
        workflow.add_edge("rewrite_query", "web_search")
        workflow.add_edge("web_search", "generate_answer")
        workflow.add_edge("generate_answer", END)

        self.graph = workflow.compile()

    def _setup_chains(self):
        """Setup LLM chains for different tasks"""
        # Document grader
        self.doc_grader = self._create_doc_grader()

        # Query rewriter
        self.query_rewriter = self._create_query_rewriter()

        # Answer generator
        self.answer_generator = self._create_answer_generator()

    def _create_doc_grader(self):
        structured_llm = self.llm.with_config({"temperature" : 0}).with_structured_output(GradeDocuments)

        sys_prompt = """You are an expert grader evaluating the relevance of a retrieved document to a user's question.
                        - If the document contains keywords or semantic meaning related to the question, grade it as relevant.
                        - Respond with only one word: "yes" if relevant, or "no" if not.
                        - Do not provide any explanation or reasoning.
                    """

        grade_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", sys_prompt),
                (
                    "human",
                    "Retrieved document: \n{document}\n\n User question : \n{question}",
                ),
            ]
        )

        return grade_prompt | structured_llm

    def _create_query_rewriter(self):
        sys_prompt = """You are a question rewriter. Your task is to optimize the input question for web search.
                        - Rewrite the question to better reflect its underlying semantic intent.
                        - Output only the rewritten question. Do not include any explanations or additional text.
                    """

        rewrite_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", sys_prompt),
                (
                    "human",
                    "Here is the initial question: \n{question}\n\n Formulate a improved question",
                ),
            ]
        )

        return rewrite_prompt | self.llm | StrOutputParser()

    def _create_answer_generator(self):
        prompt = """You are an assistant for question-answering tasks.
                    Use the following retrieved context to help answer the question.

                    - If the context is relevant, use it to answer the question.
                    - If the context is missing or unrelated, and the question is general knowledge or common sense, use your own knowledge to answer.
                    - If the question is specific and context is required to answer accurately, and no context is provided, respond with "I don't know."

                    Answer the question clearly, concisely, and accurately.

                    Question:
                    {question}

                    Context:
                    {context}

                    Answer:
                """

        prompt_template = ChatPromptTemplate.from_template(prompt)

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        return (
            {
                "context": (itemgetter("context") | RunnableLambda(format_docs)),
                "question": itemgetter("question"),
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )

    def _retrieve(self, state):
        """Retrieve documents from vector store"""
        question = state["question"]
        documents = self.retrieval_service.retrieve_documents(question)
        return {"documents": documents, "question": question}

    def _grade_documents(self, state):
        """Grade retrieved documents for relevance"""
        question = state["question"]
        documents = state["documents"]

        filtered_docs = []
        web_search_needed = "No"

        if documents:
            for doc in documents:
                score = self.doc_grader.invoke({
                    "question": question,
                    "document": doc.page_content
                })

                if score.binary_score == "yes":
                    filtered_docs.append(doc)
                else:
                    web_search_needed = "Yes"
        else:
            web_search_needed = "Yes"

        return {
            "documents": filtered_docs,
            "question": question,
            "web_search_needed": web_search_needed
        }

    def _rewrite_query(self, state):
        """Rewrite query for better web search"""
        question = state["question"]
        documents = state["documents"]

        better_question = self.query_rewriter.invoke({"question": question})
        return {"documents": documents, "question": better_question}

    def _web_search(self, state):
        """Perform web search with rewritten query"""
        question = state["question"]
        documents = state["documents"]

        # Perform web search
        web_results = self.web_search.invoke(question)
        web_content = "\n\n".join([d["content"] for d in web_results])
        web_doc = Document(page_content=web_content)
        documents.append(web_doc)

        return {"documents": documents, "question": question}

    def _generate_answer(self, state):
        """Generate final answer from context"""
        question = state["question"]
        documents = state["documents"]

        generation = self.answer_generator.invoke({
            "context": documents,
            "question": question
        })

        return {
            "documents": documents,
            "question": question,
            "generation": generation
        }

    def _decide_to_generate(self, state):
        """Decide whether to generate answer or rewrite query"""
        web_search_needed = state["web_search_needed"]

        if web_search_needed == "Yes":
            return "rewrite_query"
        else:
            return "generate_answer"

    def process_query(self, question: str, include_sources: bool = False):
        """Main RAG processing pipeline"""
        result = self.graph.invoke({"question": question})

        response = {
            "answer": result["generation"],
            "search_performed": result.get("web_search_needed") == "Yes"
        }

        if include_sources:
            response["sources"] = [
                doc.metadata.get("source", "Unknown")
                for doc in result["documents"]
            ]

        return response