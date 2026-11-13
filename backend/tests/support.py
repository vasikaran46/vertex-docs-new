import atexit
import os
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

TEST_DIRECTORY=Path(tempfile.mkdtemp(prefix="vertex-api-tests-"))
os.environ["DATABASE_URL"]="sqlite:///"+(TEST_DIRECTORY/"test.db").as_posix()
os.environ["SECRET_KEY"]="vertex-test-secret-key"
os.environ["LLM_API_KEY"]=""

from fastapi.testclient import TestClient
from app.main import app
from app.database import engine

def cleanup_test_database():
    engine.dispose()
    shutil.rmtree(TEST_DIRECTORY,ignore_errors=True)

atexit.register(cleanup_test_database)

class ApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client=TestClient(app)

    def create_account(self,name="Test User"):
        email=f"{uuid.uuid4().hex}@example.com"
        result=self.client.post("/api/auth/signup",json={"name":name,"email":email,"password":"StrongPass123"})
        self.assertEqual(result.status_code,200,result.text)
        login=self.client.post("/api/auth/login",json={"email":email,"password":"StrongPass123"})
        self.assertEqual(login.status_code,200,login.text)
        return email,login.json()["access_token"]

    @classmethod
    def tearDownClass(cls):
        engine.dispose()
