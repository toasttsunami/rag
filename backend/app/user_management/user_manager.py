import uuid
from datetime import datetime
from typing import List, Dict, Optional
from app.models import UserSession, ChatMessage, QueryResponse
from app.services.document_service import DocumentService
from app.services.retrieval_service import RetrievalService
from app.services.rag_service import RAGService

class UserManager:
    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}
        self.document_service = DocumentService()

    def create_user(self, user_id: Optional[str] = None) -> str:
        """Create a new user session"""
        if user_id is None:
            user_id = str(uuid.uuid4())

        if user_id in self.sessions:
            raise ValueError(f"User {user_id} already exists")

        # Create isolated retrieval service for this user
        retrieval_service = RetrievalService()

        session = UserSession(
            user_id=user_id,
            created_at=datetime.now(),
            retrieval_service=retrieval_service
        )

        self.sessions[user_id] = session
        return user_id

    def get_user_session(self, user_id: str) -> UserSession:
        """Get user session, create if doesn't exist"""
        if user_id not in self.sessions:
            self.create_user(user_id)
        return self.sessions[user_id]

    def add_documents_for_user(self, user_id: str, web_urls: List[str] = None,
                             local_files: List[str] = None) -> int:
        """Add documents to user's isolated document store"""
        session = self.get_user_session(user_id)

        # Load and process documents
        web_urls = web_urls or []
        local_files = local_files or []

        if not web_urls and not local_files:
            return 0

        docs = self.document_service.load_documents(web_urls, local_files)
        split_docs = self.document_service.split_documents(docs)

        # Add to user's document store
        session.documents.extend(split_docs)

        # Update user's retrieval service
        session.retrieval_service.add_documents(split_docs)

        return len(split_docs)

    def query_user_documents(self, user_id: str, question: str,
                           include_sources: bool = False) -> QueryResponse:
        """Query documents for a specific user"""
        session = self.get_user_session(user_id)

        # Create RAG service with user's retrieval service
        rag_service = RAGService(session.retrieval_service)

        # Process query
        result = rag_service.process_query(question, include_sources)

        # Create message
        message_id = str(uuid.uuid4())
        message = ChatMessage(
            message_id=message_id,
            user_id=user_id,
            timestamp=datetime.now(),
            question=question,
            answer=result["answer"],
            sources=result.get("sources"),
            search_performed=result.get("search_performed", False)
        )

        # Store in user's chat history
        session.chat_history.append(message)

        return QueryResponse(
            message_id=message_id,
            answer=result["answer"],
            sources=result.get("sources"),
            search_performed=result.get("search_performed", False)
        )

    def get_user_chat_history(self, user_id: str) -> List[ChatMessage]:
        """Get chat history for a user"""
        session = self.get_user_session(user_id)
        return session.chat_history

    def get_user_document_count(self, user_id: str) -> int:
        """Get number of documents for a user"""
        session = self.get_user_session(user_id)
        return len(session.documents)

    def delete_user(self, user_id: str) -> bool:
        """Delete user and all associated data"""
        if user_id in self.sessions:
            del self.sessions[user_id]
            return True
        return False

    def list_users(self) -> List[str]:
        """List all user IDs"""
        return list(self.sessions.keys())