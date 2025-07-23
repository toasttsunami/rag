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

# from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_tavily import TavilySearch
from app.models import GradeDocuments, GraphState
from app.services.retrieval_service import RetrievalService
from dotenv import load_dotenv
from langsmith import traceable
import sys

sys.path.append("/home/conturna/repos/projects/research-helper/backend/app/")
from prompts import *

load_dotenv()


class Config:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")


@traceable
class RAGService:
    def __init__(self, retrieval_service: RetrievalService):
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", google_api_key=Config.GOOGLE_API_KEY
        )
        self.retrieval_service = retrieval_service
        self.web_search = TavilySearch(
            max_results=5,
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
            {"rewrite_query": "rewrite_query", "generate_answer": "generate_answer"},
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
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(GradeDocuments)

        sys_prompt = DOC_GRADER_SYS_PROMPT

        grade_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", sys_prompt),
                (
                    "human",
                    "User prompt: {user_prompt}\n\nRetrieved document: {document}\n\nIs this document relevant to responding to the user's prompt?",
                ),
            ]
        )

        return grade_prompt | structured_llm

    def _create_query_rewriter(self):
        sys_prompt = QUERY_REWRITER_SYS_PROMPT

        rewrite_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", sys_prompt),
                (
                    "human",
                    "Original prompt: {user_prompt}",
                ),
            ]
        )

        return rewrite_prompt | self.llm | StrOutputParser()

    def _create_answer_generator(self):
        prompt = ANSWER_GENERATOR_PROMPT

        prompt_template = ChatPromptTemplate.from_template(prompt)

        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)

        return (
            {
                "context": (itemgetter("context") | RunnableLambda(format_docs)),
                "search_queries": itemgetter("search_queries"),
                "user_prompt": itemgetter("user_prompt"),
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )

    def _retrieve(self, state):
        """Retrieve documents from vector store"""
        user_prompt = state["user_prompt"]
        documents = self.retrieval_service.retrieve_documents(user_prompt)
        return {"documents": documents, "user_prompt": user_prompt}

    def _grade_documents(self, state):
        """Grade retrieved documents for relevance"""
        user_prompt = state["user_prompt"]
        documents = state["documents"]

        filtered_docs = []
        web_search_needed = "No"

        if documents:
            for doc in documents:
                score = self.doc_grader.invoke(
                    {"user_prompt": user_prompt, "document": doc.page_content}
                )

                if score.binary_score == "yes":
                    filtered_docs.append(doc)
                else:
                    web_search_needed = "Yes"
        else:
            web_search_needed = "Yes"

        return {
            "documents": filtered_docs,
            "user_prompt": user_prompt,
            "web_search_needed": web_search_needed,
        }

    def _rewrite_query(self, state):
        """Rewrite query for better web search"""
        user_prompt = state["user_prompt"]
        documents = state["documents"]

        search_queries = self.query_rewriter.invoke({"user_prompt": user_prompt})
        return {"documents": documents, "user_prompt": user_prompt, "search_queries": search_queries}

    def _web_search(self, state):
        """Perform web search with rewritten query"""
        user_prompt = state["user_prompt"]
        documents = state["documents"]
        search_queries = state["search_queries"]

        # Perform web search
        for query in search_queries.split('\n'):
            raw = self.web_search.invoke(query)
            results = raw.get("results", [])
            web_content = "\n\n".join(item.get("content", "") for item in results)
            # web_content = "\n\n".join([d["content"] for d in web_results])
            web_doc = Document(page_content=web_content)
            documents.append(web_doc)

        return {"documents": documents, "user_prompt": user_prompt, "search_queries": search_queries}

    def _generate_answer(self, state):
        """Generate final answer from context"""
        user_prompt = state["user_prompt"]
        documents = state["documents"]
        search_queries = state.get("search_queries", "")

        generation = self.answer_generator.invoke(
            {"context": documents, "user_prompt": user_prompt, "search_queries": search_queries}
        )

        return {"documents": documents, "user_prompt": user_prompt, "search_queries": search_queries, "generation": generation}

    def _decide_to_generate(self, state):
        """Decide whether to generate answer or rewrite query"""
        web_search_needed = state["web_search_needed"]

        if web_search_needed == "Yes":
            return "rewrite_query"
        else:
            return "generate_answer"

    def process_query(self, question: str, include_sources: bool = False):
        """Main RAG processing pipeline"""
        user_prompt = question
        result = self.graph.invoke({"user_prompt": user_prompt})

        response = {
            "answer": result["generation"],
            "search_performed": result.get("web_search_needed") == "Yes",
            "search_queries": result["search_queries"]
        }

        if include_sources:
            response["sources"] = [
                doc.metadata.get("source", "Unknown") for doc in result["documents"]
            ]

        return response
