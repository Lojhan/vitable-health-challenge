import pytest

from chatbot.features.scheduling.models import Provider
from chatbot.features.scheduling.tests.helpers import make_provider
from chatbot.features.scheduling.tools import list_providers


@pytest.mark.django_db
def test_list_providers_returns_all_seeded_providers():
    make_provider('Dr. Alice Smith', 'General Practice')
    make_provider('Dr. Bob Jones', 'Cardiology')

    result = list_providers()

    names = {p['name'] for p in result}
    assert 'Dr. Alice Smith' in names
    assert 'Dr. Bob Jones' in names
    for provider in result:
        assert 'provider_id' in provider
        assert 'specialty' in provider


@pytest.mark.django_db
def test_list_providers_returns_empty_when_no_providers_exist():
    Provider.objects.all().delete()
    assert list_providers() == []
