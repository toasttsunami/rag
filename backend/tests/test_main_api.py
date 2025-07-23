import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

TEST_PDF_DIR = "test_files"
TEST_PDF_FILENAME = "test.pdf"

def test_create_user(test_client: TestClient):
    """Test user creation endpoint."""
    response = test_client.post("/users/create", params={"user_id": "test_user_1"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "test_user_1"}

    # Test creating a duplicate user
    response = test_client.post("/users/create", params={"user_id": "test_user_1"})
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]

@patch('app.user_management.user_manager.UserManager.add_documents_for_user')
def test_upload_documents_url(mock_add_docs, test_client: TestClient):
    """Test document upload via URL."""
    test_client.post("/users/create", params={"user_id": "test_user_2"})
    mock_add_docs.return_value = 10  # Simulate adding 10 document chunks

    response = test_client.post(
        "/documents/upload",
        data={
            "user_id": "test_user_2",
            "urls": "http://example.com"
        }
    )
    assert response.status_code == 201
    assert response.json() == {"message": "Successfully added 10 document chunks."}
    # Check if the mocked function was called correctly
    mock_add_docs.assert_called_with(
        user_id="test_user_2",
        web_urls=["http://example.com"],
        local_files=[]
    )

@patch('app.user_management.user_manager.UserManager.add_documents_for_user')
def test_upload_documents_file(mock_add_docs, test_client: TestClient, create_test_pdf):
    """Test document upload via file."""
    test_client.post("/users/create", params={"user_id": "test_user_3"})
    mock_add_docs.return_value = 5

    file_path = os.path.join(TEST_PDF_DIR, TEST_PDF_FILENAME)
    with open(file_path, "rb") as f:
        response = test_client.post(
            "/documents/upload",
            data={"user_id": "test_user_3"},
            files={"files": (TEST_PDF_FILENAME, f, "application/pdf")}
        )

    assert response.status_code == 201
    assert response.json() == {"message": "Successfully added 5 document chunks."}
    # Check if the arguments to the mocked function contain the path to the uploaded file
    args, kwargs = mock_add_docs.call_args
    assert kwargs['user_id'] == 'test_user_3'
    assert 'uploaded_files/test.pdf' in kwargs['local_files'][0]


# Mock the entire RAG service for query testing
@patch('app.user_management.user_manager.RAGService')
def test_query_endpoint(MockRAGService, test_client: TestClient):
    """Test the /query endpoint."""
    # Setup a mock instance and its process_query method
    mock_rag_instance = MockRAGService.return_value
    mock_rag_instance.process_query.return_value = {
        "answer": "This is a mocked answer.",
        "sources": ["mock_source_1"],
        "search_performed": False
    }

    # Create user first
    test_client.post("/users/create", params={"user_id": "test_user_4"})

    query_data = {
        "user_id": "test_user_4",
        "question": "What is life?",
        "include_sources": True
    }
    response = test_client.post("/query", json=query_data)

    assert response.status_code == 200
    json_response = response.json()
    assert json_response["answer"] == "This is a mocked answer."
    assert json_response["sources"] == ["mock_source_1"]
    assert "message_id" in json_response


@patch('app.user_management.user_manager.RAGService')
def test_get_history(MockRAGService, test_client: TestClient):
    """Test the chat history endpoint by making real queries that are mocked at a lower level."""
    user_id = "test_user_5"
    test_client.post("/users/create", params={"user_id": user_id})

    # --- First Query ---
    mock_rag_instance = MockRAGService.return_value
    mock_rag_instance.process_query.return_value = {
        "answer": "Answer to the first question.",
        "sources": [],
        "search_performed": False
    }
    response1 = test_client.post("/query", json={"user_id": user_id, "question": "First question"})
    assert response1.status_code == 200

    # --- Second Query ---
    mock_rag_instance.process_query.return_value = {
        "answer": "Answer to the second question.",
        "sources": [],
        "search_performed": True
    }
    response2 = test_client.post("/query", json={"user_id": user_id, "question": "Second question"})
    assert response2.status_code == 200

    # --- Get History ---
    response = test_client.get(f"/users/{user_id}/history")
    assert response.status_code == 200
    history = response.json()
    
    assert len(history) == 2
    assert history[0]["question"] == "First question"
    assert history[0]["answer"] == "Answer to the first question."
    assert history[1]["question"] == "Second question"
    assert history[1]["answer"] == "Answer to the second question."
    assert history[1]["search_performed"] is True