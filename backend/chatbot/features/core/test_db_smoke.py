import pytest
from django.db import connection


@pytest.mark.django_db
def test_db_smoke_connection_is_available():
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1')
        row = cursor.fetchone()

    assert row == (1,)
