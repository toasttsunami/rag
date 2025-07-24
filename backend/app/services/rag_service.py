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
        workflow.add_node("classify_query", self._classify_query)
        workflow.add_node("detect_followup", self._detect_followup)
        workflow.add_node("contextualize_query", self._contextualize_query)
        workflow.add_node("route_by_classification", lambda state: state)
        workflow.add_node("handle_conversation", self._handle_conversation)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("grade_documents", self._grade_documents)
        workflow.add_node("rewrite_query", self._rewrite_query)
        workflow.add_node("web_search", self._web_search)
        workflow.add_node("generate_answer", self._generate_answer)
        
        # Set entry point
        workflow.set_entry_point("classify_query")
        
        # Add edges
        workflow.add_edge("classify_query", "detect_followup")
        workflow.add_conditional_edges(
            "detect_followup",
            self._route_based_on_followup,
            {
                "contextualize": "contextualize_query",
                "direct": "route_by_classification"
            }
        )
        workflow.add_edge("contextualize_query", "route_by_classification")
        workflow.add_conditional_edges(
            "route_by_classification",
            self._route_based_on_classification,
            {
                "conversation": "handle_conversation",
                "research": "retrieve",
                "general": "generate_answer"
            }
        )
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
            max_tokens=10000,
            tavily_api_key=Config.TAVILY_API_KEY,
        )
        
        self._setup_chains()
        self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)
        
        # Add nodes
        workflow.add_node("classify_query", self._classify_query)
        workflow.add_node("detect_followup", self._detect_followup)
        workflow.add_node("contextualize_query", self._contextualize_query)
        workflow.add_node("route_by_classification", lambda state: state)
        workflow.add_node("handle_conversation", self._handle_conversation)
        workflow.add_node("retrieve", self._retrieve)
        workflow.add_node("grade_documents", self._grade_documents)
        workflow.add_node("rewrite_query", self._rewrite_query)
        workflow.add_node("web_search", self._web_search)
        workflow.add_node("generate_answer", self._generate_answer)
        
        # Set entry point
        workflow.set_entry_point("classify_query")
        
        # Add edges
        workflow.add_edge("classify_query", "detect_followup")
        workflow.add_conditional_edges(
            "detect_followup",
            self._route_based_on_followup,
            {
                "contextualize": "contextualize_query",
                "direct": "route_by_classification"
            }
        )
        workflow.add_edge("contextualize_query", "route_by_classification")
        workflow.add_conditional_edges(
            "route_by_classification",
            self._route_based_on_classification,
            {
                "conversation": "handle_conversation",
                "research": "retrieve",
                "general": "generate_answer"
            }
        )
        
        workflow.add_edge("handle_conversation", END)
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
        # Query classifier
        self.query_classifier = self._create_query_classifier()
        # Follow-up detector
        self.followup_detector = self._create_followup_detector()
        # Query contextualizer
        self.query_contextualizer = self._create_query_contextualizer()
        # Conversation handler
        self.conversation_handler = self._create_conversation_handler()
        # Document grader
        self.doc_grader = self._create_doc_grader()
        # Query rewriter
        self.query_rewriter = self._create_query_rewriter()
        # Answer generator
        self.answer_generator = self._create_answer_generator()

    def _create_query_classifier(self):
        """Create query classifier to determine intent"""
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(QueryClassification)
        
        classify_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_CLASSIFIER_SYS_PROMPT),
            ("human", "User input: {user_prompt}")
        ])
        
        return classify_prompt | structured_llm

    def _create_followup_detector(self):
        """Create follow-up question detector"""
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(FollowUpDetection)
        
        followup_prompt = ChatPromptTemplate.from_messages([
            ("system", FOLLOWUP_DETECTOR_SYS_PROMPT),
            ("human", "Current query: {user_prompt}\n\nRecent conversation:\n{chat_context}")
        ])
        
        return followup_prompt | structured_llm

    def _create_query_contextualizer(self):
        """Create query contextualizer for follow-up questions"""
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_CONTEXTUALIZER_SYS_PROMPT),
            ("human", "Original query: {user_prompt}\n\nChat history context:\n{chat_context}\n\nConversation summary: {conversation_summary}")
        ])
        
        return contextualize_prompt | self.llm | StrOutputParser()

    def _create_conversation_handler(self):
        """Create conversation handler for casual chat"""
        conversation_prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_HANDLER_SYS_PROMPT),
            ("human", "Current message: {user_prompt}\n\nRecent conversation:\n{chat_context}")
        ])
        
        return conversation_prompt | self.llm | StrOutputParser()

    def _create_doc_grader(self):
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(GradeDocuments)
        
        grade_prompt = ChatPromptTemplate.from_messages([
            ("system", DOC_GRADER_SYS_PROMPT),
            ("human", "User prompt: {user_prompt}\n\nRetrieved document: {document}\n\nIs this document relevant to responding to the user's prompt?"),
        ])
        
        return grade_prompt | structured_llm

    def _create_query_rewriter(self):
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_REWRITER_SYS_PROMPT),
            ("human", "Original prompt: {user_prompt}"),
        ])
        
        return rewrite_prompt | self.llm | StrOutputParser()

    def _create_answer_generator(self):
        prompt_template = ChatPromptTemplate.from_template(ANSWER_GENERATOR_PROMPT)
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)
        
        return (
            {
                "context": (itemgetter("context") | RunnableLambda(format_docs)),
                "search_queries": itemgetter("search_queries"),
                "user_prompt": itemgetter("user_prompt"),
                "chat_context": itemgetter("chat_context"),
                "conversation_summary": itemgetter("conversation_summary"),
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )

    def _format_chat_context(self, chat_history: List[ChatMessage], max_messages: int = 5) -> str:
        """Format recent chat history for context"""
        if not chat_history:
            return "No previous conversation."
        
        # Get recent messages
        recent_messages = chat_history[-max_messages:]
        
        context_lines = []
        for msg in recent_messages:
            context_lines.append(f"User: {msg.question}")
            context_lines.append(f"Assistant: {msg.answer}")
        
        return "\n".join(context_lines)

    def _classify_query(self, state):
        """Classify the query to determine the appropriate handling"""
        user_prompt = state["user_prompt"]
        classification = self.query_classifier.invoke({"user_prompt": user_prompt})
        
        return {
            **state,
            "query_type": classification.query_type,
            "confidence": classification.confidence
        }

    def _detect_followup(self, state):
        """Detect if this is a follow-up question"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        
        if not chat_history:
            return {
                **state,
                "is_followup": False,
                "followup_confidence": 0.0
            }
        
        chat_context = self._format_chat_context(chat_history)
        detection = self.followup_detector.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        return {
            **state,
            "is_followup": detection.is_followup,
            "followup_confidence": detection.confidence
        }

    def _contextualize_query(self, state):
        """Contextualize query with chat history for follow-up questions"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        conversation_summary = state.get("conversation_summary", "")
        
        chat_context = self._format_chat_context(chat_history)
        
        contextualized_query = self.query_contextualizer.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context,
            "conversation_summary": conversation_summary
        })
        
        return {
            **state,
            "contextualized_query": contextualized_query
        }

    def _handle_conversation(self, state):
        """Handle conversational/casual inputs"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        
        chat_context = self._format_chat_context(chat_history)
        
        response = self.conversation_handler.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        return {
            **state,
            "generation": response
        }

    def _route_based_on_followup(self, state):
        """Route based on follow-up detection"""
        is_followup = state.get("is_followup", False)
        followup_confidence = state.get("followup_confidence", 0.0)
        
        if is_followup and followup_confidence > 0.7:
            return "contextualize"
        else:
            return "direct"

    def _route_based_on_classification(self, state):
        """Route to appropriate handler based on classification"""
        query_type = state["query_type"]
        confidence = state.get("confidence", 0.5)
        
        # If confidence is low, default to general handling
        if confidence < 0.7:
            return "general"
        
        return query_type

    def _retrieve(self, state):
        """Retrieve documents from vector store"""
        # Use contextualized query if available, otherwise original
        query = state.get("contextualized_query", state["user_prompt"])
        documents = self.retrieval_service.retrieve_documents(query)
        return {**state, "documents": documents}

    def _grade_documents(self, state):
        """Grade retrieved documents for relevance"""
        query = state.get("contextualized_query", state["user_prompt"])
        documents = state["documents"]
        filtered_docs = []
        web_search_needed = "No"
        
        if documents:
            for doc in documents:
                score = self.doc_grader.invoke(
                    {"user_prompt": query, "document": doc.page_content}
                )
                if score.binary_score == "yes":
                    filtered_docs.append(doc)
                else:
                    web_search_needed = "Yes"
        else:
            web_search_needed = "Yes"
        
        return {
            **state,
            "documents": filtered_docs,
            "web_search_needed": web_search_needed,
        }

    def _rewrite_query(self, state):
        """Rewrite query for better web search"""
        query = state.get("contextualized_query", state["user_prompt"])
        search_queries = self.query_rewriter.invoke({"user_prompt": query})
        return {**state, "search_queries": search_queries}

    def _web_search(self, state):
        """Perform web search with rewritten query"""
        documents = state["documents"]
        search_queries = state["search_queries"]
        
        # Perform web search
        for query in search_queries.split('\n'):
            if query.strip():  # Skip empty queries
                raw = self.web_search.invoke(query)
                results = raw.get("results", [])
                web_content = "\n\n".join(item.get("content", "") for item in results)
                web_doc = Document(page_content=web_content)
                documents.append(web_doc)
        
        return {**state, "documents": documents}

    def _generate_answer(self, state):
        """Generate final answer from context or general knowledge"""
        user_prompt = state["user_prompt"]
        documents = state.get("documents", [])
        search_queries = state.get("search_queries", "")
        query_type = state.get("query_type", "general")
        chat_history = state.get("chat_history", [])
        conversation_summary = state.get("conversation_summary", "")
        
        chat_context = self._format_chat_context(chat_history)
        
        # For general queries without context, use a simpler prompt
        if query_type == "general" and not documents:
            simple_prompt = ChatPromptTemplate.from_template(
                "You are a helpful AI assistant. Consider the conversation context if relevant.\n\n"
                "Recent conversation:\n{chat_context}\n\n"
                "Current question: {user_prompt}\n\n"
                "Answer naturally and conversationally:"
            )
            generation = (simple_prompt | self.llm | StrOutputParser()).invoke({
                "user_prompt": user_prompt,
                "chat_context": chat_context
            })
        else:
            generation = self.answer_generator.invoke({
                "context": documents,
                "user_prompt": user_prompt,
                "search_queries": search_queries,
                "chat_context": chat_context,
                "conversation_summary": conversation_summary
            })
        
        return {
            **state,
            "generation": generation
        }

    def _decide_to_generate(self, state):
        """Decide whether to generate answer or rewrite query"""
        web_search_needed = state["web_search_needed"]
        if web_search_needed == "Yes":
            return "rewrite_query"
        else:
            return "generate_answer"

    def process_query_with_history(self, question: str, user_id: str, chat_history: List[ChatMessage], 
                                 conversation_summary: str = "", include_sources: bool = False):
        """Main RAG processing pipeline with chat history"""
        
        result = self.graph.invoke({
            "user_prompt": question,
            "user_id": user_id,
            "chat_history": chat_history,
            "conversation_summary": conversation_summary
        })
        
        response = {
            "answer": result["generation"],
            "query_type": result.get("query_type", "unknown"),
            "is_followup": result.get("is_followup", False),
            "search_performed": result.get("web_search_needed") == "Yes",
            "search_queries": result.get("search_queries", ""),
            "context_used": result.get("contextualized_query", "")
        }
        
        if include_sources and result.get("documents"):
            response["sources"] = [
                doc.metadata.get("source", "Unknown") for doc in result["documents"]
            ]
        
        return response

    # Keep backward compatibility
    def process_query(self, question: str, include_sources: bool = False):
        """Original method for backward compatibility"""
        return self.process_query_with_history(question, "", [], "", include_sources)
        workflow.add_edge("handle_conversation", END)
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
        # Query classifier
        self.query_classifier = self._create_query_classifier()
        # Follow-up detector
        self.followup_detector = self._create_followup_detector()
        # Query contextualizer
        self.query_contextualizer = self._create_query_contextualizer()
        # Conversation handler
        self.conversation_handler = self._create_conversation_handler()
        # Document grader
        self.doc_grader = self._create_doc_grader()
        # Query rewriter
        self.query_rewriter = self._create_query_rewriter()
        # Answer generator
        self.answer_generator = self._create_answer_generator()

    def _create_query_classifier(self):
        """Create query classifier to determine intent"""
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(QueryClassification)
        
        classify_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_CLASSIFIER_SYS_PROMPT),
            ("human", "User input: {user_prompt}")
        ])
        
        return classify_prompt | structured_llm

    def _create_followup_detector(self):
        """Create follow-up question detector"""
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(FollowUpDetection)
        
        followup_prompt = ChatPromptTemplate.from_messages([
            ("system", FOLLOWUP_DETECTOR_SYS_PROMPT),
            ("human", "Current query: {user_prompt}\n\nRecent conversation:\n{chat_context}")
        ])
        
        return followup_prompt | structured_llm

    def _create_query_contextualizer(self):
        """Create query contextualizer for follow-up questions"""
        contextualize_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_CONTEXTUALIZER_SYS_PROMPT),
            ("human", "Original query: {user_prompt}\n\nChat history context:\n{chat_context}\n\nConversation summary: {conversation_summary}")
        ])
        
        return contextualize_prompt | self.llm | StrOutputParser()

    def _create_conversation_handler(self):
        """Create conversation handler for casual chat"""
        conversation_prompt = ChatPromptTemplate.from_messages([
            ("system", CONVERSATION_HANDLER_SYS_PROMPT),
            ("human", "Current message: {user_prompt}\n\nRecent conversation:\n{chat_context}")
        ])
        
        return conversation_prompt | self.llm | StrOutputParser()

    def _create_doc_grader(self):
        structured_llm = self.llm.with_config(
            {"temperature": 0}
        ).with_structured_output(GradeDocuments)
        
        grade_prompt = ChatPromptTemplate.from_messages([
            ("system", DOC_GRADER_SYS_PROMPT),
            ("human", "User prompt: {user_prompt}\n\nRetrieved document: {document}\n\nIs this document relevant to responding to the user's prompt?"),
        ])
        
        return grade_prompt | structured_llm

    def _create_query_rewriter(self):
        rewrite_prompt = ChatPromptTemplate.from_messages([
            ("system", QUERY_REWRITER_SYS_PROMPT),
            ("human", "Original prompt: {user_prompt}"),
        ])
        
        return rewrite_prompt | self.llm | StrOutputParser()

    def _create_answer_generator(self):
        prompt_template = ChatPromptTemplate.from_template(ANSWER_GENERATOR_PROMPT)
        
        def format_docs(docs):
            return "\n\n".join(doc.page_content for doc in docs)
        
        return (
            {
                "context": (itemgetter("context") | RunnableLambda(format_docs)),
                "search_queries": itemgetter("search_queries"),
                "user_prompt": itemgetter("user_prompt"),
                "chat_context": itemgetter("chat_context"),
                "conversation_summary": itemgetter("conversation_summary"),
            }
            | prompt_template
            | self.llm
            | StrOutputParser()
        )

    def _format_chat_context(self, chat_history: List[ChatMessage], max_messages: int = 5) -> str:
        """Format recent chat history for context"""
        if not chat_history:
            return "No previous conversation."
        
        # Get recent messages
        recent_messages = chat_history[-max_messages:]
        
        context_lines = []
        for msg in recent_messages:
            context_lines.append(f"User: {msg.question}")
            context_lines.append(f"Assistant: {msg.answer}")
        
        return "\n".join(context_lines)

    def _classify_query(self, state):
        """Classify the query to determine the appropriate handling"""
        user_prompt = state["user_prompt"]
        classification = self.query_classifier.invoke({"user_prompt": user_prompt})
        
        return {
            **state,
            "query_type": classification.query_type,
            "confidence": classification.confidence
        }

    def _detect_followup(self, state):
        """Detect if this is a follow-up question"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        
        if not chat_history:
            return {
                **state,
                "is_followup": False,
                "followup_confidence": 0.0
            }
        
        chat_context = self._format_chat_context(chat_history)
        detection = self.followup_detector.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        return {
            **state,
            "is_followup": detection.is_followup,
            "followup_confidence": detection.confidence
        }

    def _contextualize_query(self, state):
        """Contextualize query with chat history for follow-up questions"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        conversation_summary = state.get("conversation_summary", "")
        
        chat_context = self._format_chat_context(chat_history)
        
        contextualized_query = self.query_contextualizer.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context,
            "conversation_summary": conversation_summary
        })
        
        return {
            **state,
            "contextualized_query": contextualized_query
        }

    def _handle_conversation(self, state):
        """Handle conversational/casual inputs"""
        user_prompt = state["user_prompt"]
        chat_history = state.get("chat_history", [])
        
        chat_context = self._format_chat_context(chat_history)
        
        response = self.conversation_handler.invoke({
            "user_prompt": user_prompt,
            "chat_context": chat_context
        })
        
        return {
            **state,
            "generation": response
        }

    def _route_based_on_followup(self, state):
        """Route based on follow-up detection"""
        is_followup = state.get("is_followup", False)
        followup_confidence = state.get("followup_confidence", 0.0)
        
        if is_followup and followup_confidence > 0.7:
            return "contextualize"
        else:
            return "direct"

    def _route_based_on_classification(self, state):
        """Route to appropriate handler based on classification"""
        query_type = state["query_type"]
        confidence = state.get("confidence", 0.5)
        
        # If confidence is low, default to general handling
        if confidence < 0.7:
            return "general"
        
        return query_type

    def _retrieve(self, state):
        """Retrieve documents from vector store"""
        # Use contextualized query if available, otherwise original
        query = state.get("contextualized_query", state["user_prompt"])
        documents = self.retrieval_service.retrieve_documents(query)
        return {**state, "documents": documents}

    def _grade_documents(self, state):
        """Grade retrieved documents for relevance"""
        query = state.get("contextualized_query", state["user_prompt"])
        documents = state["documents"]
        filtered_docs = []
        web_search_needed = "No"
        
        if documents:
            for doc in documents:
                score = self.doc_grader.invoke(
                    {"user_prompt": query, "document": doc.page_content}
                )
                if score.binary_score == "yes":
                    filtered_docs.append(doc)
                else:
                    web_search_needed = "Yes"
        else:
            web_search_needed = "Yes"
        
        return {
            **state,
            "documents": filtered_docs,
            "web_search_needed": web_search_needed,
        }

    def _rewrite_query(self, state):
        """Rewrite query for better web search"""
        query = state.get("contextualized_query", state["user_prompt"])
        search_queries = self.query_rewriter.invoke({"user_prompt": query})
        return {**state, "search_queries": search_queries}

    def _web_search(self, state):
        """Perform web search with rewritten query"""
        documents = state["documents"]
        search_queries = state["search_queries"]
        
        # Perform web search
        for query in search_queries.split('\n'):
            if query.strip():  # Skip empty queries
                raw = self.web_search.invoke(query)
                results = raw.get("results", [])
                web_content = "\n\n".join(item.get("content", "") for item in results)
                web_doc = Document(page_content=web_content)
                documents.append(web_doc)
        
        return {**state, "documents": documents}

    def _generate_answer(self, state):
        """Generate final answer from context or general knowledge"""
        user_prompt = state["user_prompt"]
        documents = state.get("documents", [])
        search_queries = state.get("search_queries", "")
        query_type = state.get("query_type", "general")
        chat_history = state.get("chat_history", [])
        conversation_summary = state.get("conversation_summary", "")
        
        chat_context = self._format_chat_context(chat_history)
        
        # For general queries without context, use a simpler prompt
        if query_type == "general" and not documents:
            simple_prompt = ChatPromptTemplate.from_template(
                "You are a helpful AI assistant. Consider the conversation context if relevant.\n\n"
                "Recent conversation:\n{chat_context}\n\n"
                "Current question: {user_prompt}\n\n"
                "Answer naturally and conversationally:"
            )
            generation = (simple_prompt | self.llm | StrOutputParser()).invoke({
                "user_prompt": user_prompt,
                "chat_context": chat_context
            })
        else:
            generation = self.answer_generator.invoke({
                "context": documents,
                "user_prompt": user_prompt,
                "search_queries": search_queries,
                "chat_context": chat_context,
                "conversation_summary": conversation_summary
            })
        
        return {
            **state,
            "generation": generation
        }

    def _decide_to_generate(self, state):
        """Decide whether to generate answer or rewrite query"""
        web_search_needed = state["web_search_needed"]
        if web_search_needed == "Yes":
            return "rewrite_query"
        else:
            return "generate_answer"

    def process_query_with_history(self, question: str, user_id: str, chat_history: List[ChatMessage], 
                                 conversation_summary: str = "", include_sources: bool = False):
        """Main RAG processing pipeline with chat history"""
        
        result = self.graph.invoke({
            "user_prompt": question,
            "user_id": user_id,
            "chat_history": chat_history,
            "conversation_summary": conversation_summary
        })
        
        response = {
            "answer": result["generation"],
            "query_type": result.get("query_type", "unknown"),
            "is_followup": result.get("is_followup", False),
            "search_performed": result.get("web_search_needed") == "Yes",
            "search_queries": result.get("search_queries", ""),
            "context_used": result.get("contextualized_query", "")
        }
        
        if include_sources and result.get("documents"):
            response["sources"] = [
                doc.metadata.get("source", "Unknown") for doc in result["documents"]
            ]
        
        return response

    # Keep backward compatibility
    def process_query(self, question: str, include_sources: bool = False):
        """Original method for backward compatibility"""
        return self.process_query_with_history(question, "", [], "", include_sources)