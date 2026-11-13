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
