import os
import pytest
from pathlib import Path
import json

from project.app import app, db

TEST_DB = "test.db"


@pytest.fixture
def client():
    BASE_DIR = Path(__file__).resolve().parent.parent
    app.config["TESTING"] = True
    app.config["DATABASE"] = BASE_DIR.joinpath(TEST_DB)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR.joinpath(TEST_DB)}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.create_all()  # setup
        yield app.test_client()  # tests run here
        db.drop_all()  # teardown


def login(client, username, password):
    """Login helper function"""
    return client.post(
        "/login",
        data=dict(username=username, password=password),
        follow_redirects=True,
    )


def logout(client):
    """Logout helper function"""
    return client.get("/logout", follow_redirects=True)


def test_index(client):
    response = client.get("/", content_type="html/text")
    assert response.status_code == 200


def test_database(client):
    """initial test. ensure that the database exists"""
    tester = Path("test.db").is_file()
    assert tester


def test_empty_db(client):
    """Ensure database is blank"""
    rv = client.get("/")
    assert b"No entries yet. Add some!" in rv.data


def test_login_logout(client):
    """Test login and logout using helper functions"""
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"])
    assert b"You were logged in" in rv.data
    rv = logout(client)
    assert b"You were logged out" in rv.data
    rv = login(client, app.config["USERNAME"] + "x", app.config["PASSWORD"])
    assert b"Invalid username" in rv.data
    rv = login(client, app.config["USERNAME"], app.config["PASSWORD"] + "x")
    assert b"Invalid password" in rv.data


def test_messages(client):
    """Ensure that user can post messages"""
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="<Hello>", text="<strong>HTML</strong> allowed here"),
        follow_redirects=True,
    )
    assert b"No entries here so far" not in rv.data
    assert b"&lt;Hello&gt;" in rv.data
    assert b"<strong>HTML</strong> allowed here" in rv.data

def test_delete_message(client):
    """Ensure the messages are being deleted"""
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 0
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    assert data["status"] == 1


def test_delete_requires_login(client):
    """Ensure deleting a post requires the user to be logged in"""
    # Attempt to delete without logging in
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    # Should fail because user is not logged in
    assert data["status"] == 0

    # Log in
    login(client, app.config["USERNAME"], app.config["PASSWORD"])

    # Attempt to delete again (assuming post 1 exists)
    rv = client.get("/delete/1")
    data = json.loads(rv.data)
    # Should succeed
    assert data["status"] == 1
    assert data["message"] == "Post Deleted"

    

def test_search_with_query(client):
    """Access /search/ with a query parameter after adding a post"""
    # Log in and add a post
    login(client, app.config["USERNAME"], app.config["PASSWORD"])
    rv = client.post(
        "/add",
        data=dict(title="Test Post", text="Some content"),
        follow_redirects=True,
    )
    assert b"New entry was successfully posted" in rv.data

    # Search with a query
    rv = client.get("/search/", query_string={"query": "Test"})
    assert rv.status_code == 200
    # The added post should appear
    assert b"Test Post" in rv.data
    assert b"Some content" in rv.data

    # Search with a query that doesn't match
    rv = client.get("/search/", query_string={"query": "Nonexistent"})
    assert rv.status_code == 200
    # Depending on template, might show "No entries yet" or just no posts
    # If your template lists entries, just check it doesn't include the post
    assert b"Test Post" not in rv.data