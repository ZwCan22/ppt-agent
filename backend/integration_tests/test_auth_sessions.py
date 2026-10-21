"""Real password verification, session cookie lookup, expiration and revocation."""

from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, select, update

from integration_tests.support import TaskApiTestCase


class AuthSessionTests(TaskApiTestCase):
    def setUp(self):
        super().setUp()
        from app.api.auth import router
        from app.core.security import SESSION_COOKIE_NAME
        from app.models.user_session import UserSession
        self.SessionModel = UserSession
        self.cookie_name = SESSION_COOKIE_NAME
        self.app.include_router(router, prefix="/api")
        self.app.dependency_overrides.pop(self.current_user_dependency)
        self.credentials = {
            "username": f"auth_{uuid4().hex[:20]}",
            "password": "Only-for-local-tests-2026!",
        }
        response = self.client.post("/api/auth/register", json=self.credentials)
        self.assertEqual(response.status_code, 201, response.text)
        self.user_id = response.json()["id"]

    def login(self):
        response = self.client.post("/api/auth/login", json=self.credentials)
        self.assertEqual(response.status_code, 200, response.text)
        return response

    def test_login_me_and_cookie_contract(self):
        response = self.login()
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertIn("path=/api", cookie)
        me = self.client.get("/api/auth/me")
        self.assertEqual(me.status_code, 200, me.text)
        self.assertEqual(me.json()["id"], self.user_id)
        self.assertNotIn("password_hash", me.json())
        token = self.client.cookies.get(self.cookie_name)
        session = self.db.scalar(select(self.SessionModel).where(
            self.SessionModel.user_id == UUID(self.user_id),
        ))
        self.assertIsNotNone(session)
        self.assertNotEqual(session.token_hash, token)

    def test_expired_session_is_rejected(self):
        self.login()
        self.db.execute(update(self.SessionModel).where(
            self.SessionModel.user_id == UUID(self.user_id),
        ).values(
            expires_at=func.now() - timedelta(seconds=1),
        ))
        self.db.flush()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)

    def test_logout_revokes_old_cookie_on_server(self):
        self.login()
        old_token = self.client.cookies.get(self.cookie_name)
        result = self.client.post("/api/auth/logout")
        self.assertEqual(result.status_code, 204)
        self.client.cookies.clear()
        self.client.cookies.set(self.cookie_name, old_token, path="/api")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        self.assertEqual(self.session_count(), 0)

    def test_wrong_password_does_not_create_session(self):
        result = self.client.post("/api/auth/login", json={
            **self.credentials, "password": "Definitely-wrong-password",
        })
        self.assertEqual(result.status_code, 401)
        self.assertEqual(self.session_count(), 0)

    def session_count(self):
        return self.db.scalar(select(func.count()).select_from(self.SessionModel).where(
            self.SessionModel.user_id == UUID(self.user_id),
        ))

    def test_disabled_user_session_is_rejected(self):
        self.login()
        self.db.execute(update(self.User).where(self.User.id == UUID(self.user_id)).values(is_active=False))
        self.db.flush()
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
