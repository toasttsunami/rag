from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from typing import List
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
        logger.error("Exception occured calling /users/create: ", exc_info=True)
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
        logger.error("Exception occured calling /documents/upload: ", exc_info=True)
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
        logger.error("Exception occured calling /query: ", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/users/{user_id}/history")
def get_history(user_id: str):
    try:
        history = user_manager.get_user_chat_history(user_id)
        return history
    except Exception as e:
        logger.error(f"Exception occured calling /users/{user_id}/history: ", exc_info=True)
        raise HTTPException(status_code=404, detail=f"User not found: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)