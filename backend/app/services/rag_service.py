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
from langchain_tavily import TavilySearch
from app.models import GradeDocuments, GraphState, QueryClassification, FollowUpDetection, ChatMessage
from app.services.retrieval_service import RetrievalService
from dotenv import load_dotenv
from langsmith import traceable
import sys
from app.prompts import *
import asyncio

from concurrent.futures import ThreadPoolExecutor, as_completed
import time

load_dotenv()

class Config:
    GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
    TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")

@traceable
class RAGService:
    def __init__(self, retrieval_service: RetrievalService):
        #TODO: implement a fast and slower (dynamic thinking) model to optimize budget allocation
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash", google_api_key=Config.GOOGLE_API_KEY
        )
        self.retrieval_service = retrieval_service
        self.web_search = TavilySearch(
            max_results=3,
            search_depth="advanced",
            max_tokens=2000,
            tavily_api_key=Config.TAVILY_API_KEY,
        )

        self.executor = ThreadPoolExecutor(max_workers=4)
        self._setup_chains()
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("classify_and_detect", self._classify_and_detect)
        workflow.add_node("contextualize_query", self._contextualize_query)
        workflow.add_node("handle_conversation", self._handle_conversation)
        workflow.add_node("retrieve_and_grade", self._retrieve_and_grade)
        workflow.add_node("web_search", self._web_search)
        workflow.add_node("generate_answer", self._generate_answer)
        
        # Set entry point
        workflow.set_entry_point("classify_and_detect")
        
        # Add edges
        workflow.add_conditional_edges(
            "classify_and_detect",
            self._smart_route,
            {
                "conversation": "handle_conversation",
                "contextualize": "contextualize_query",
                "retrieve": "retrieve_and_grade",
                "direct": "generate_answer"
            }
        )
        workflow.add_edge("contextualize_query", "retrieve_and_grade")
        workflow.add_edge("handle_conversation", END)
        workflow.add_conditional_edges(
            "retrieve_and_grade",
            self._decide_web_search,
            {"web_search": "web_search", "generate": "generate_answer"}
        )
        workflow.add_edge("web_search", "generate_answer")
        workflow.add_edge("generate_answer", END)
        
        self.graph = workflow.compile()

    def _setup_chains(self):
        self.combined_classifier = self._create_combined_classifier()
        self.query_contextualizer = self._create_query_contextualizer()
        self.query_rewriter = self._create_query_rewriter()
        self.conversation_handler = self._create_conversation_handler()
        self.answer_generator = self._create_answer_generator()

    def _create_combined_classifier(self):
        """Single LLM call for both classification and follow-up detection"""
        combined_prompt = ChatPromptTemplate.from_messages([
            ("system", COMBINED_CLASSIFIER_PROMPT),
            ("human", "Current query: {user_prompt}\n\nRecent conversation:\n{chat_context}")
        ])
        
        return combined_prompt | self.llm | StrOutputParser()

    def _create_query_contextualizer(self):
        """Optimized contextualizer"""
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_CONTEXTUALIZER_SYS_PROMPT),
            ("human", "Query: {user_prompt}\nContext: {chat_context}")
        ])
        
        return contextualize_prompt | self.llm | StrOutputParser()

    def _create_conversation_handler(self):
        """Fast conversation handler"""
        conversation_prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_HANDLER_SYS_PROMPT),
            ("human", "{user_prompt}")
        ])
        
        return conversation_prompt | self.llm | StrOutputParser()

    def _create_query_rewriter(self):
        rewrite_prmopt = ChatPromptTemplate.from_messages([
            ("system", QUERY_REWRITER_SYS_PROMPT),
            ("human", "Original Prmopt: {user_prompt}, Relevant Documents: {documents}")
        ])

        return rewrite_prmopt | self.llm | StrOutputParser()

    def _create_answer_generator(self):
        """Optimized answer generator"""
        prompt_template = ChatPromptTemplate.from_template(OPTIMIZED_ANSWER_PROMPT)
        
        def format_docs(docs):
            if not docs:
                return "No specific context available."
            # Limit context size for speed
            return "\n\n".join(doc.page_content[:1000] for doc in docs[:5])
        
        return (
            {
                "context": (itemgetter("context") | RunnableLambda(format_docs)),
                "user_prompt": itemgetter("user_prompt"),
                "chat_context": itemgetter("chat_context"),
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )

    def _format_chat_context(self, chat_history: List[ChatMessage], max_messages: int = 3) -> str:
        """Optimized context formatting"""
        if not chat_history:
            return "No previous conversation."
        
        recent_messages = chat_history[-max_messages:]
        context_lines = []
        for msg in recent_messages:
            # Truncate long messages
            question = msg.question[:500] + "..." if len(msg.question) > 500 else msg.question
            answer = msg.answer[:700] + "..." if len(msg.answer) > 300 else msg.answer
            context_lines.append(f"Q: {question}\nA: {answer}")
        
        return "\n".join(context_lines)

    def _classify_and_detect(self, state):
        """Single LLM call for classification and follow-up detection"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        
        chat_context = self._format_chat_context(chat_history)
        
        # Single LLM call for both tasks
        result = self.combined_classifier.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        # Parse the structured response
        try:
            lines = result.strip().split('\n')
            query_type = lines[0].split(':')[1].strip() if ':' in lines[0] else "general"
            is_followup = lines[1].split(':')[1].strip().lower() == "true" if len(lines) > 1 else False
            confidence = float(lines[2].split(':')[1].strip()) if len(lines) > 2 else 0.8
        except:
            # Fallback
            query_type = "general"
            is_followup = any(word in user_prompt.lower() for word in ["it", "this", "that", "what about"])
            confidence = 0.5
        
        return {
            **state,
            "query_type": query_type,
            "is_followup": is_followup,
            "confidence": confidence
        }

    def _smart_route(self, state):
        """Intelligent routing based on combined classification"""
        query_type = state["query_type"]
        is_followup = state.get("is_followup", False)
        confidence = state.get("confidence", 0.5)
        
        # Fast paths
        if query_type == "conversation" and confidence > 0.7:
            return "conversation"
        
        if is_followup and confidence > 0.6:
            return "contextualize"
        
        if query_type == "research" or confidence > 0.8:
            return "retrieve"
        
        return "general"

    def _retrieve_and_grade(self, state):
        """Parallel retrieval and grading for speed"""
        query = state.get("contextualized_query", state["user_prompt"])
        
        # Retrieve documents
        documents = self.retrieval_service.retrieve_documents(query)
        
        if not documents:
            return {
                **state,
                "documents": [],
                "web_search_needed": True
            }
        
        # Parallel grading with threading
        def grade_doc(doc):
            # Simple relevance check instead of LLM for speed
            query_words = set(query.lower().split())
            doc_words = set(doc.page_content.lower().split())
            overlap = len(query_words.intersection(doc_words))
            return doc if overlap >= 2 else None  # Simple heuristic
        
        # Grade documents in parallel
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(grade_doc, doc) for doc in documents[:10]]  # Limit for speed
            filtered_docs = [f.result() for f in as_completed(futures) if f.result()]
        
        web_search_needed = len(filtered_docs) < 2  # Need web search if few relevant docs
        
        return {
            **state,
            "documents": filtered_docs,
            "web_search_needed": web_search_needed
        }

    def _web_search(self, state):
        """Optimized web search with single query"""
        query = state.get("contextualized_query", state["user_prompt"])
        documents = state.get("documents", [])        
        search_query = self.query_rewriter.invoke({"user_prompt" : query, "documents": documents})
        
        try:
            raw = self.web_search.invoke(search_query)
            results = raw.get("results", [])
            # print(results)
            
            if results:
                for item in results:
                    web_content = "\n\n".join(item.get("content", ""))
                    web_doc = Document(
                        page_content=web_content,
                        metadata={
                            'title': item.get("title"),
                            'source': item.get("url")
                        }
                    )
                    documents.append(web_doc)
        except Exception as e:
            # Graceful degradation - continue without web search
            print(f"Web search failed: {e}")
        
        return {**state, "documents": documents}

    def _decide_web_search(self, state):
        """Decision on web search"""
        web_search_needed = state.get("web_search_needed", False)
        documents = state.get("documents", [])
        
        if state.get("query_type") == "research":
            return "web_search"

        # Skip web search if we have enough context or for conversation
        if len(documents) >= 3 or state.get("query_type") == "conversation":
            return "generate"
        
        return "web_search" if web_search_needed else "generate"

    def _contextualize_query(self, state):
        """Query contextualization"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        
        chat_context = self._format_chat_context(chat_history, max_messages=5)
        
        contextualized_query = self.query_contextualizer.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        return {**state, "contextualized_query": contextualized_query}

    def _handle_conversation(self, state):
        """Conversation handling"""
        user_prompt = state["user_prompt"]
        response = self.conversation_handler.invoke({"user_prompt": user_prompt})
        
        return {**state, "generation": response}

    def _generate_answer(self, state):
        """Answer generation"""
        user_prompt = state["user_prompt"]
        documents = state.get("documents", [])
        chat_history = state.get("chat_history", [])
        
        chat_context = self._format_chat_context(chat_history, max_messages=2)
        
        generation = self.answer_generator.invoke({
            "context": documents,
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        return {**state, "generation": generation}

    async def process_query_async(self, question: str, user_id: str, chat_history: List[ChatMessage], 
                                conversation_summary: str = "", include_sources: bool = False):
        """Async version for better performance"""
                
        start_time = time.time()
        
        result = self.graph.invoke({
            "user_prompt": question,
            "user_id": user_id,
            "chat_history": chat_history,
            "conversation_summary": conversation_summary
        })
        
        processing_time = time.time() - start_time
        
        response = {
            "answer": result["generation"],
            "query_type": result.get("query_type", "unknown"),
            "is_followup": result.get("is_followup", False),
            "search_performed": result.get("web_search_needed", False),
            "processing_time": round(processing_time, 2)
        }
        
        if include_sources and result.get("documents"):
            response["sources"] = [
                doc.metadata.get("source", "Unknown") for doc in result["documents"][:5]
            ]
        
        # Cache non-conversational results
        # if result.get("query_type") != "conversation":
            # self.cache.set(question, user_id, response)
        
        return response

    def process_query_with_history(self, question: str, user_id: str, chat_history: List[ChatMessage], 
                                 conversation_summary: str = "", include_sources: bool = False):
        """Synchronous wrapper for async method"""
        return asyncio.run(self.process_query_async(
            question, user_id, chat_history, conversation_summary, include_sources
        ))