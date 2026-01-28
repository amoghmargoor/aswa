import pytest
from uuid import uuid4
from fastapi.testclient import TestClient

from aswa_query.app import app
from aswa_query.config import Settings


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tenant_id():
    return uuid4()


@pytest.fixture
def headers(tenant_id):
    return {"X-Tenant-ID": str(tenant_id)}


@pytest.fixture
def settings():
    return Settings()
