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

    def _generate_conversation_summary(self, chat_history: List[ChatMessage]) -> str:
        """Generate a summary of the conversation for context"""
        if not chat_history:
            return ""
        
        # Simple summary - you could make this more sophisticated
        recent_topics = []
        for msg in chat_history[-3:]:  # Last 3 exchanges
            if len(msg.question) > 10:  # Skip very short questions
                recent_topics.append(msg.question)
        
        if recent_topics:
            return f"Recent discussion topics: {'; '.join(recent_topics)}"
        return ""

    def query_user_documents(self, user_id: str, question: str,
                           include_sources: bool = False) -> QueryResponse:
        """Query documents for a specific user with chat history support"""
        session = self.get_user_session(user_id)
        session.last_activity = datetime.now()

        # Create RAG service with user's retrieval service
        rag_service = RAGService(session.retrieval_service)

        # Generate conversation summary if needed
        conversation_summary = self._generate_conversation_summary(session.chat_history)

        # Process query with chat history
        result = rag_service.process_query_with_history(
            question=question,
            user_id=user_id,
            chat_history=session.chat_history,
            conversation_summary=conversation_summary,
            include_sources=include_sources
        )

        # Create message with enhanced metadata
        message_id = str(uuid.uuid4())
        message = ChatMessage(
            message_id=message_id,
            user_id=user_id,
            timestamp=datetime.now(),
            question=question,
            answer=result["answer"],
            sources=result.get("sources"),
            search_performed=result.get("search_performed", False),
            query_type=result.get("query_type"),
            context_used=result.get("context_used")
        )

        # Store in user's chat history
        session.chat_history.append(message)

        # Update conversation summary if needed (every 5 messages)
        if len(session.chat_history) % 5 == 0:
            session.conversation_summary = self._generate_conversation_summary(session.chat_history)

        return QueryResponse(
            message_id=message_id,
            answer=result["answer"],
            sources=result.get("sources"),
            search_performed=result.get("search_performed", False),
            query_type=result.get("query_type"),
            is_followup=result.get("is_followup"),
            context_used=result.get("context_used")
        )

    def get_user_chat_history(self, user_id: str, limit: Optional[int] = None) -> List[ChatMessage]:
        """Get chat history for a user with optional limit"""
        session = self.get_user_session(user_id)
        if limit:
            return session.chat_history[-limit:]
        return session.chat_history

    def get_recent_context(self, user_id: str, max_messages: int = 5) -> List[ChatMessage]:
        """Get recent messages for context"""
        session = self.get_user_session(user_id)
        return session.chat_history[-max_messages:] if session.chat_history else []

    def clear_user_history(self, user_id: str) -> bool:
        """Clear chat history for a user"""
        session = self.get_user_session(user_id)
        session.chat_history.clear()
        session.conversation_summary = None
        return True

    def get_conversation_summary(self, user_id: str) -> str:
        """Get conversation summary for a user"""
        session = self.get_user_session(user_id)
        return session.conversation_summary or ""

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

    def get_user_stats(self, user_id: str) -> Dict:
        """Get comprehensive stats for a user"""
        session = self.get_user_session(user_id)
        return {
            "user_id": user_id,
            "created_at": session.created_at.isoformat(),
            "last_activity": session.last_activity.isoformat(),
            "total_messages": len(session.chat_history),
            "total_documents": len(session.documents),
            "conversation_active": len(session.chat_history) > 0
        }