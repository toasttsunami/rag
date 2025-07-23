import pytest
from fastapi.testclient import TestClient
from app.main import app, user_manager
from app.user_management.user_manager import UserManager
import os

# Create a dummy PDF file for upload tests
TEST_PDF_FILENAME = "test.pdf"
TEST_PDF_DIR = "test_files"

@pytest.fixture(scope="session", autouse=True)
def create_test_pdf():
    """Create a dummy PDF file for testing uploads."""
    os.makedirs(TEST_PDF_DIR, exist_ok=True)
    file_path = os.path.join(TEST_PDF_DIR, TEST_PDF_FILENAME)
    # A minimal PDF content
    pdf_content = b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 3 3]>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000058 00000 n\n0000000111 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n149\n%%EOF"
    with open(file_path, "wb") as f:
        f.write(pdf_content)
    yield file_path
    # Teardown: remove the file and directory
    os.remove(file_path)
    os.rmdir(TEST_PDF_DIR)


@pytest.fixture(scope="function")
def test_client() -> TestClient:
    """
    Creates a new FastAPI TestClient for each test function.
    This fixture also resets the user_manager to ensure tests are isolated.
    """
    # Reset the user manager before each test
    app.dependency_overrides[user_manager] = UserManager()
    client = TestClient(app)
    yield client
    # Clean up after the test
    app.dependency_overrides = {}