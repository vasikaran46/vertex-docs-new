from tests.support import ApiTestCase

class DocumentPrivacyTests(ApiTestCase):
    def test_documents_persist_and_remain_private_to_their_owner(self):
        email,owner_token=self.create_account("Document Owner")
        owner={"Authorization":f"Bearer {owner_token}"}
        upload=self.client.post(
            "/api/documents/upload",
            headers=owner,
            files={"file":("private-notes.txt",b"Only the owner should see these notes.","text/plain")},
        )
        self.assertEqual(upload.status_code,200,upload.text)
        document_id=upload.json()["id"]
        self.assertEqual([item["name"] for item in self.client.get("/api/documents",headers=owner).json()],["private-notes.txt"])

        self.client.post("/api/auth/logout",headers=owner)
        restored_login=self.client.post("/api/auth/login",json={"email":email,"password":"StrongPass123"})
        self.assertEqual(restored_login.status_code,200,restored_login.text)
        restored={"Authorization":f"Bearer {restored_login.json()['access_token']}"}
        download=self.client.get(f"/api/documents/{document_id}/download",headers=restored)
        self.assertEqual(download.status_code,200,download.text)
        self.assertIn(b"Only the owner",download.content)

        _,other_token=self.create_account("Another User")
        other={"Authorization":f"Bearer {other_token}"}
        self.assertEqual(self.client.get("/api/documents",headers=other).json(),[])
        self.assertEqual(self.client.get(f"/api/documents/{document_id}/download",headers=other).status_code,404)
        self.assertEqual(self.client.delete(f"/api/documents/{document_id}",headers=restored).status_code,200)
        self.assertEqual(self.client.get("/api/documents",headers=restored).json(),[])
