import pytest
from pydantic import ValidationError

from orion.api.interactive.signup_manager.model.signup_request_model import SignupRequest


def test_signup_request_defaults_tenant_type_to_client():
    payload = SignupRequest(username="tenantusr1", email="tenant@company.com", password="StrongPass1!")
    assert payload.tenant_type == "client"


@pytest.mark.parametrize("tenant_type", ["guard", "client", "service_provider"])
def test_signup_request_accepts_allowed_tenant_types(tenant_type):
    payload = SignupRequest(
        username="tenantusr1",
        email="tenant@company.com",
        password="StrongPass1!",
        tenant_type=tenant_type,
    )
    assert payload.tenant_type == tenant_type


def test_signup_request_rejects_invalid_tenant_type():
    with pytest.raises(ValidationError):
        SignupRequest(
            username="tenantusr1",
            email="tenant@company.com",
            password="StrongPass1!",
            tenant_type="invalid_type",
        )
