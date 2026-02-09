from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime

from odmantic import Model, EmbeddedModel, Field
from pydantic import BaseModel, model_validator


class IocCategory(EmbeddedModel):
    ioc_id: str
    name: Optional[str] = ""
    values: List[str] = []

    def __str__(self):
        return f"{self.name} ({len(self.values)} values)"


class TenantStatus(str, Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    DISABLE = "disable"


class TenantType(str, Enum):
    ADMIN = "admin"
    SERVICE_PROVIDER = "service_provider"
    CLIENT = "client"
    GUARD = "guard"


class SecurityLicenseType(str, Enum):
    SECURITY_GUARD = "securityGuard"
    PRIVATE_INVESTIGATOR = "privateInvestigator"
    DUAL_SECURITY_GUARD_PRIVATE_INVESTIGATOR = "dualSecurityGuardPrivateInvestigator"


class PoliceClearanceAuthorityType(str, Enum):
    MUNICIPAL_POLICE_SERVICE = "municipalPoliceService"
    PROVINCIAL_POLICE_SERVICE = "provincialPoliceService"
    RCMP = "rcmp"
    RCMP_ACCREDITED_PROVIDER = "rcmpAccreditedProvider"
    FIRST_NATIONS_POLICE_SERVICE = "firstNationsPoliceService"
    OTHER = "other"


class TrainingCertificateType(str, Enum):
    BASIC_SECURITY_TRAINING = "basicSecurityTraining"
    STANDARD_FIRST_AID_CPR_AED = "standardFirstAidCprAed"
    USE_OF_FORCE_DEFENSIVE_TACTICS = "useOfForceDefensiveTactics"
    DE_ESCALATION_CONFLICT_MANAGEMENT = "deEscalationConflictManagement"
    WHMIS = "whmis"
    BATON_HANDCUFF_TRAINING = "batonHandcuffTraining"
    OTHER = "other"


class TrainingIssuerType(str, Enum):
    PROVINCIAL_APPROVED_TRAINING_PROVIDER = "provincialApprovedTrainingProvider"
    PRIVATE_SECURITY_ACADEMY_APPROVED = "privateSecurityAcademyApproved"
    ST_JOHN_AMBULANCE = "stJohnAmbulance"
    TRAINING_PROVIDER_ACCREDITED = "trainingProviderAccredited"
    WORKPLACE_APPROVED_TRAINING_PROVIDER = "workplaceApprovedTrainingProvider"
    OTHER = "other"


# Common embedded models
class Address(EmbeddedModel):
    street: str = ""
    city: str = ""
    country: str = ""
    province: str = ""
    postal_code: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ContactPerson(EmbeddedModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    designation: Optional[str] = None


# Guard profile structures
class GuardDocumentType(str, Enum):
    CNIC = "cnic"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    PROVINCIAL_ID = "provincial_id"
    CANADIAN_PASSPORT = "canadian_passport"
    PR_CARD = "pr_card"
    WORK_PERMIT = "work_permit"
    STUDY_PERMIT = "study_permit"


class GuardAvailability(EmbeddedModel):
    morning: bool = False
    afternoon: bool = False
    night: bool = False


class GuardLicense(EmbeddedModel):
    license_number: str = ""
    issuing_authority: str = ""
    expiry_date: Optional[datetime] = None
    document_url: Optional[str] = None


class GuardSecurityLicense(EmbeddedModel):
    full_legal_name: str = ""
    license_number: str = ""
    license_type: Optional[SecurityLicenseType] = None
    issuing_province: str = ""
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    document_file_id: Optional[str] = None
    document_file_url: Optional[str] = None
    document_file_name: Optional[str] = None
    document_file_mime_type: Optional[str] = None
    document_file_size: Optional[int] = None


class GuardIdentification(EmbeddedModel):
    id_type: Optional[GuardDocumentType] = None
    id_number: str = ""
    document_url: Optional[str] = None


class GuardBackgroundCheck(EmbeddedModel):
    status: Optional[str] = None  # pending/approved/rejected
    document_url: Optional[str] = None
    verified_date: Optional[datetime] = None
    verified_by: Optional[str] = None


class GuardPoliceClearance(EmbeddedModel):
    issuing_authority: Optional[PoliceClearanceAuthorityType] = None
    issuing_authority_other: Optional[str] = None
    issuing_province: str = ""
    issuing_city: Optional[str] = None
    issue_date: Optional[datetime] = None
    reference_number: Optional[str] = None
    document_file_id: Optional[str] = None
    document_file_url: Optional[str] = None
    document_file_name: Optional[str] = None
    document_file_mime_type: Optional[str] = None
    document_file_size: Optional[int] = None


class GuardTrainingCertificate(EmbeddedModel):
    certificate_name: Optional[TrainingCertificateType] = None
    issuing_organization: Optional[TrainingIssuerType] = None
    issuing_organization_other: Optional[str] = None
    issue_date: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    document_file_id: Optional[str] = None
    document_file_url: Optional[str] = None
    document_file_name: Optional[str] = None
    document_file_mime_type: Optional[str] = None
    document_file_size: Optional[int] = None


class GuardProfile(EmbeddedModel):
    full_name: str = ""
    date_of_birth: Optional[datetime] = None
    home_address: Address = Address()
    profile_picture_url: Optional[str] = None
    identification: GuardIdentification = GuardIdentification()
    security_license: GuardLicense = GuardLicense()
    security_licenses: List[GuardSecurityLicense] = []
    police_clearances: List[GuardPoliceClearance] = []
    training_certificates: List[GuardTrainingCertificate] = []
    background_check: GuardBackgroundCheck = GuardBackgroundCheck()
    max_travel_radius_km: Optional[int] = None
    weekly_availability: GuardAvailability = GuardAvailability()
    preferred_guard_types: List[str] = []
    service_provider_id: Optional[str] = None
    hourly_rate: Optional[float] = None
    shift_rate: Optional[float] = None


# Client profile structures
class ClientSite(EmbeddedModel):
    site_id: str = ""
    site_name: str = ""
    site_address: Address = Address()
    site_manager_contact: str = ""
    manager_email: str = ""
    number_of_guards_required: Optional[int] = None
    site_type: Optional[str] = None  # office/warehouse/event/residential


class ClientProfile(EmbeddedModel):
    legal_entity_name: str = ""
    business_type: Optional[str] = None
    company_registration_number: str = ""
    company_logo_url: Optional[str] = None
    primary_contact: ContactPerson = ContactPerson()
    billing_address: Address = Address()
    tax_vat_number: Optional[str] = None
    sites: List[ClientSite] = []
    preferred_guard_types: List[str] = []
    billing_model: str = "per_hour"  # per_hour/per_shift
    subscription_tier: str = "basic"


# Service provider profile structures
class OperatingRegion(EmbeddedModel):
    city: str = ""
    country: str = ""
    coverage_radius_km: Optional[int] = None


class SecurityLicense(EmbeddedModel):
    license_number: str = ""
    issuing_authority: str = ""
    expiry_date: Optional[datetime] = None
    document_url: Optional[str] = None


class InsurancePolicy(EmbeddedModel):
    policy_number: str = ""
    coverage_amount: Optional[float] = None
    currency: str = "USD"
    expiry_date: Optional[datetime] = None
    document_url: Optional[str] = None
    coverage_details: Optional[str] = None


class ServiceProviderProfile(EmbeddedModel):
    legal_company_name: str = ""
    trading_name: Optional[str] = None
    company_registration_number: str = ""
    year_of_establishment: Optional[int] = None
    company_logo_url: Optional[str] = None
    company_website: Optional[str] = None
    head_office_address: Address = Address()
    company_phone: str = ""
    company_email: str = ""
    primary_representative: ContactPerson = ContactPerson()
    security_license: SecurityLicense = SecurityLicense()
    insurance_details: InsurancePolicy = InsurancePolicy()
    tax_registration_number: Optional[str] = None
    operating_regions: List[OperatingRegion] = []
    guard_categories_offered: List[str] = []
    default_billing_model: str = "per_hour"
    guard_count: int = 0
    subscription_tier: str = "basic"
    emergency_contact: str = ""


class db_tenant_model(Model):
    # Common/base fields (cross-domain)
    subscription: bool = False
    is_default: bool = False
    verified: bool = False
    user_quota: int = 0
    status: TenantStatus = TenantStatus.DISABLE
    licenses: List[str] = []
    iocs: List[IocCategory] = []

    # Tenant type and typed profile (contains all domain-specific fields)
    tenant_type: TenantType = Field(default=TenantType.CLIENT)
    profile: Optional[Dict[str, Any]] = Field(default=None)

    # Auditing/metadata
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    verified_date: Optional[datetime] = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def _backfill_defaults(cls, values):
        # Defensive defaults for legacy documents
        if isinstance(values, dict):
            values.setdefault("tenant_type", TenantType.CLIENT)
            values.setdefault("profile", None)
            if not values.get("created_at"):
                values["created_at"] = datetime.utcnow()
            if not values.get("updated_at"):
                values["updated_at"] = datetime.utcnow()
            if values.get("verified") and not values.get("verified_date"):
                values["verified_date"] = datetime.utcnow()
        return values


class TenantRequest(BaseModel):
    id: str = "-1"
    iocs: List[IocCategory] = []
    name: str
    phone: str = ""
    country: str = ""
    subscription: bool = False
    city: str = ""
    postal_code: str = ""
    verified: Optional[bool] = None
    user_quota: Optional[int] = None
    status: Optional[TenantStatus] = None
    licenses: List[str] = []


class TenantPayload(BaseModel):
    """Unified request/response model for tenant GET/POST/PUT operations.
    All domain-specific fields are in the typed profile; no duplication.
    """
    id: Optional[str] = None
    tenant_type: TenantType = TenantType.CLIENT
    profile: Optional[Dict[str, Any]] = None
    subscription: bool = False
    verified: bool = False
    user_quota: int = 0
    status: TenantStatus = TenantStatus.DISABLE
    licenses: List[str] = []
    iocs: List[IocCategory] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    verified_date: Optional[datetime] = None
