from fastapi import FastAPI, HTTPException, UploadFile, File
from typing import List
from app.models import QueryRequest, QueryResponse, DocumentUploadRequest
from app.user_management.user_manager import UserManager
import os
import shutil

app = FastAPI()
user_manager = UserManager()

UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/users/create")
def create_user(user_id: str = None):
    try:
        new_user_id = user_manager.create_user(user_id)
        return {"user_id": new_user_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/documents/upload", status_code=201)
async def upload_documents(
    user_id: str,
    urls: List[str] = [],
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
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/history")
def get_history(user_id: str):
    try:
        history = user_manager.get_user_chat_history(user_id)
        return history
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)