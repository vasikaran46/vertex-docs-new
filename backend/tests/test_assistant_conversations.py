from tests.support import ApiTestCase


class AssistantConversationTests(ApiTestCase):
    def test_conversations_are_private_listable_and_deletable(self):
        _,owner_token=self.create_account("Owner")
        _,other_token=self.create_account("Other")
        owner={"Authorization":f"Bearer {owner_token}"}
        other={"Authorization":f"Bearer {other_token}"}

        created=self.client.post("/api/ai/conversations",headers=owner)
        self.assertEqual(created.status_code,200,created.text)
        conversation_id=created.json()["id"]
        self.assertEqual(len(self.client.get("/api/ai/conversations",headers=owner).json()),1)
        self.assertEqual(self.client.get(f"/api/ai/conversations/{conversation_id}",headers=owner).status_code,200)
        self.assertEqual(self.client.get(f"/api/ai/conversations/{conversation_id}",headers=other).status_code,404)
        self.assertEqual(self.client.delete(f"/api/ai/conversations/{conversation_id}",headers=other).status_code,404)
        self.assertEqual(self.client.delete(f"/api/ai/conversations/{conversation_id}",headers=owner).status_code,200)
        self.assertEqual(self.client.get("/api/ai/conversations",headers=owner).json(),[])

    def test_chat_attachment_text_extracts_supported_document_text(self):
        _,token=self.create_account()
        response=self.client.post(
            "/api/ai/chat/attachment-text",
            headers={"Authorization":f"Bearer {token}"},
            files={"file":("notes.txt",b"Meeting notes for the project","text/plain")},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["text"],"Meeting notes for the project")

    def test_new_theme_ids_persist_in_preferences(self):
        _,token=self.create_account()
        response=self.client.put(
            "/api/settings/preferences",
            headers={"Authorization":f"Bearer {token}"},
            json={"theme":"deep-teal-dark"},
        )
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()["theme"],"deep-teal-dark")

    def test_chat_sessions_crud_and_privacy(self):
        # 1. Create two separate accounts
        _, owner_token = self.create_account("ChatOwner")
        _, other_token = self.create_account("ChatOther")
        owner = {"Authorization": f"Bearer {owner_token}"}
        other = {"Authorization": f"Bearer {other_token}"}

        # 2. Unauthorized access returns 401
        self.assertEqual(self.client.get("/api/chat/sessions").status_code, 401)
        self.assertEqual(self.client.post("/api/chat/sessions", json={"title": "Test"}).status_code, 401)

        # 3. Create session for owner
        created = self.client.post("/api/chat/sessions", headers=owner, json={"title": "Research on Quantum"})
        self.assertEqual(created.status_code, 200, created.text)
        sess_data = created.json()
        sess_id = sess_data["id"]
        self.assertEqual(sess_data["title"], "Research on Quantum")

        # 4. Other user creates their own session
        other_created = self.client.post("/api/chat/sessions", headers=other, json={"title": "Other User's Chat"})
        self.assertEqual(other_created.status_code, 200)
        other_sess_id = other_created.json()["id"]

        # 5. List only own sessions
        owner_sessions = self.client.get("/api/chat/sessions", headers=owner).json()
        self.assertEqual(len(owner_sessions), 1)
        self.assertEqual(owner_sessions[0]["id"], sess_id)
        self.assertEqual(owner_sessions[0]["title"], "Research on Quantum")

        other_sessions = self.client.get("/api/chat/sessions", headers=other).json()
        self.assertEqual(len(other_sessions), 1)
        self.assertEqual(other_sessions[0]["id"], other_sess_id)

        # 6. Messages persist and return in order
        m1 = self.client.post(
            f"/api/chat/sessions/{sess_id}/messages",
            headers=owner,
            json={"role": "user", "content": "What is entanglement?"},
        )
        self.assertEqual(m1.status_code, 200, m1.text)
        m2 = self.client.post(
            f"/api/chat/sessions/{sess_id}/messages",
            headers=owner,
            json={"role": "assistant", "content": "Quantum entanglement is a phenomenon..."},
        )
        self.assertEqual(m2.status_code, 200, m2.text)
        m3 = self.client.post(
            f"/api/chat/sessions/{sess_id}/messages",
            headers=owner,
            json={"role": "user", "content": "Can it be used for communication?"},
        )
        self.assertEqual(m3.status_code, 200, m3.text)

        detail = self.client.get(f"/api/chat/sessions/{sess_id}", headers=owner)
        self.assertEqual(detail.status_code, 200)
        detail_data = detail.json()
        self.assertEqual(len(detail_data["messages"]), 3)
        self.assertEqual(detail_data["messages"][0]["role"], "user")
        self.assertEqual(detail_data["messages"][0]["content"], "What is entanglement?")
        self.assertEqual(detail_data["messages"][1]["role"], "assistant")
        self.assertEqual(detail_data["messages"][2]["content"], "Can it be used for communication?")

        # 7. Cross-user isolation: other user gets 404 when trying to read/write/rename/delete owner's session
        self.assertEqual(self.client.get(f"/api/chat/sessions/{sess_id}", headers=other).status_code, 404)
        self.assertEqual(
            self.client.post(f"/api/chat/sessions/{sess_id}/messages", headers=other, json={"role": "user", "content": "hack"}).status_code,
            404,
        )
        self.assertEqual(
            self.client.patch(f"/api/chat/sessions/{sess_id}", headers=other, json={"title": "Hacked"}).status_code,
            404,
        )
        self.assertEqual(self.client.delete(f"/api/chat/sessions/{sess_id}", headers=other).status_code, 404)

        # 8. Rename session
        renamed = self.client.patch(
            f"/api/chat/sessions/{sess_id}",
            headers=owner,
            json={"title": "Quantum Physics Notes"},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["title"], "Quantum Physics Notes")

        # 9. Delete cascade
        del_resp = self.client.delete(f"/api/chat/sessions/{sess_id}", headers=owner)
        self.assertEqual(del_resp.status_code, 200)
        # Session is gone
        self.assertEqual(self.client.get(f"/api/chat/sessions/{sess_id}", headers=owner).status_code, 404)
        self.assertEqual(len(self.client.get("/api/chat/sessions", headers=owner).json()), 0)
