
import pytest

from app import create_app, db


@pytest.fixture(scope="module")
def app():
    """Create one Flask application for the test module."""
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite://",
    })

    yield application

    with application.app_context():
        db.drop_all()


@pytest.fixture()
def client(app):
    """Provide a clean database for every test."""
    with app.app_context():
        db.drop_all()
        db.create_all()

    with app.test_client() as test_client:
        yield test_client


def test_homepage_loads(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Lost something" in response.data


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "healthy"


def test_registration_and_login(client):
    response = client.post("/register", data={
        "name": "Test Student",
        "email": "student@example.com",
        "password": "password123",
    }, follow_redirects=True)

    assert response.status_code == 200

    response = client.post("/login", data={
        "email": "student@example.com",
        "password": "password123",
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Hello, Test" in response.data


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
