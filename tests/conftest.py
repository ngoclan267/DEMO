import os
import tempfile

import pytest

# Test dung SQLite tam thoi rieng, khong dung chung file DB that (data/social_listening.db)
# de tests khong lam bay/trung du lieu crawl that va nguoc lai.
_tmp_db_fd, _tmp_db_path = tempfile.mkstemp(suffix=".db")
os.close(_tmp_db_fd)
os.environ["SQLITE_PATH"] = _tmp_db_path
# Tat scheduler trong test: khong de test tu dong goi crawl mang that.
os.environ["ENABLE_SCHEDULER"] = "false"

from fastapi.testclient import TestClient
from src.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
