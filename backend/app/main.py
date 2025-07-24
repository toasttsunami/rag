from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from app.models import QueryRequest, QueryResponse, DocumentUploadRequest
from app.user_management.user_manager import UserManager
import os
import shutil
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # allow_origins=[
    #     "http://localhost:3000",
    #     "http://192.168.29.9:3000"
    #     ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

user_manager = UserManager()

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/users/create")
def create_user(user_id: str = None):
    try:
        new_user_id = user_manager.create_user(user_id)
        return {"user_id": new_user_id}
    except ValueError as e:
        logger.error("Exception occurred calling /users/create: ", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/documents/upload", status_code=201)
async def upload_documents(
    user_id: str = Form(...),
    urls: List[str] = Form([]),
    files: List[UploadFile] = File([])
):
    file_paths = []
    try:
        for file in files:
            file_path = os.path.join(UPLOAD_DIR, file.filename)
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_paths.append(file_path)

        docs_added = user_manager.add_documents_for_user(
            user_id=user_id,
            web_urls=urls,
            local_files=file_paths
        )
        return {"message": f"Successfully added {docs_added} document chunks."}
    except Exception as e:
        logger.error("Exception occurred calling /documents/upload: ", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        # Clean up uploaded files
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)

@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest):
    try:
        response = user_manager.query_user_documents(
            user_id=request.user_id,
            question=request.question,
            include_sources=request.include_sources
        )
        return response
    except Exception as e:
        logger.error("Exception occurred calling /query: ", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/history")
def get_history(user_id: str, limit: Optional[int] = Query(None, description="Limit number of messages returned")):
    try:
        history = user_manager.get_user_chat_history(user_id, limit)
        return {"messages": history}
    except Exception as e:
        logger.error(f"Exception occurred calling /users/{user_id}/history: ", exc_info=True)
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.get("/users/{user_id}/context")
def get_recent_context(user_id: str, max_messages: int = Query(5, description="Number of recent messages for context")):
    """Get recent conversation context for a user"""
    try:
        context = user_manager.get_recent_context(user_id, max_messages)
        return {"context": context}
    except Exception as e:
        logger.error(f"Exception occurred calling /users/{user_id}/context: ", exc_info=True)
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.delete("/users/{user_id}/history")
def clear_history(user_id: str):
    """Clear chat history for a user"""
    try:
        success = user_manager.clear_user_history(user_id)
        if success:
            return {"message": "Chat history cleared successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error(f"Exception occurred calling DELETE /users/{user_id}/history: ", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/summary")
def get_conversation_summary(user_id: str):
    """Get conversation summary for a user"""
    try:
        summary = user_manager.get_conversation_summary(user_id)
        return {"summary": summary}
    except Exception as e:
        logger.error(f"Exception occurred calling /users/{user_id}/summary: ", exc_info=True)
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.get("/users/{user_id}/stats")
def get_user_stats(user_id: str):
    """Get comprehensive stats for a user"""
    try:
        stats = user_manager.get_user_stats(user_id)
        return stats
    except Exception as e:
        logger.error(f"Exception occurred calling /users/{user_id}/stats: ", exc_info=True)
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")

@app.get("/users")
def list_users():
    """List all users"""
    try:
        users = user_manager.list_users()
        return {"users": users}
    except Exception as e:
        logger.error("Exception occurred calling /users: ", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    """Delete a user and all associated data"""
    try:
        success = user_manager.delete_user(user_id)
        if success:
            return {"message": f"User {user_id} deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="User not found")
    except Exception as e:
        logger.error(f"Exception occurred calling DELETE /users/{user_id}: ", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)