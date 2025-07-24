import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any, TypedDict, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from langchain_core.documents import Document

class GradeDocuments(BaseModel):
    """Binary score for relevance check on retrieved documents"""
    binary_score: str = Field(
        description="Documents are relevant to the question yes or no"
    )


class FollowUpDetection(BaseModel):
    """Detection of whether query is a follow-up question"""
    is_followup: bool = Field(
        description="Whether this query is a follow-up to previous conversation"
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1 for the detection"
    )
    referenced_context: Optional[str] = Field(
        description="What previous context this query is referring to, if any"
    )


@dataclass
class ChatMessage:
    """Represents a single chat message"""
    message_id: str
    user_id: str
    timestamp: datetime
    question: str
    answer: str
    sources: Optional[List[str]] = None
    search_performed: bool = False
    query_type: Optional[str] = None
    context_used: Optional[str] = None

@dataclass
class UserSession:
    """Represents a user session with isolated data"""
    user_id: str
    created_at: datetime
    documents: List[Document] = field(default_factory=list)
    chat_history: List[ChatMessage] = field(default_factory=list)
    retrieval_service: Optional[Any] = None
    last_actiity: datetime = field(default_factory=datetime.now)
    conversation_summary: Optional[str] = None

class QueryRequest(BaseModel):
    user_id: str
    question: str
    include_sources: bool = False

class QueryResponse(BaseModel):
    message_id: str
    answer: str
    sources: Optional[List[str]] = None
    search_performed: bool = False
    query_type: Optional[str] = None
    is_followup: Optional[bool] = None
    context_used: Optional[str] = None

class DocumentUploadRequest(BaseModel):
    user_id: str
    urls: List[str] = []
    file_paths: List[str] = []

class QueryClassification(BaseModel):
    """Classification of uesr query type"""
    query_type: Literal["conversation", "research", "general"] = Field(
        description="Type of query: 'conversation' for greetings/casual chat, 'research' for specific information needs, 'general' for simple questions"
    )
    confidence: float = Field(
        description="Confidence score between 0 and 1 for the classification"
    )
    reasoning: str = Field(
        description="Brief explanation for the classification"
    )

class GraphState(TypedDict):
    """Represents the state of our graph"""
    user_prompt: str
    documents: List[Document]
    generation: str
    web_search_needed: str
    search_queries: str
    query_type: str
    confidence: float
    chat_history: List[ChatMessage]
    is_followup: bool
    followup_confidence: float
    contextualized_query: str
    conversation_summary: str