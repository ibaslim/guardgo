from typing import Dict, List

from orion.services.mongo_manager.shared_model.db_tenant_model import (
    GuardDocumentType,
    SecurityLicenseType,
    PoliceClearanceAuthorityType,
    TrainingCertificateType,
    TrainingIssuerType,
    ClientType,
    ClientSiteType,
    ClientGuardType,
)

Option = Dict[str, str]

COUNTRY_OPTIONS: List[Option] = [
    {"value": "CA", "label": "Canada"},
    {"value": "US", "label": "United States"},
    {"value": "MX", "label": "Mexico"},
    {"value": "GB", "label": "United Kingdom"},
    {"value": "IE", "label": "Ireland"},
    {"value": "FR", "label": "France"},
    {"value": "DE", "label": "Germany"},
    {"value": "IT", "label": "Italy"},
    {"value": "ES", "label": "Spain"},
    {"value": "NL", "label": "Netherlands"},
    {"value": "BE", "label": "Belgium"},
    {"value": "CH", "label": "Switzerland"},
    {"value": "AT", "label": "Austria"},
    {"value": "SE", "label": "Sweden"},
    {"value": "NO", "label": "Norway"},
    {"value": "DK", "label": "Denmark"},
    {"value": "FI", "label": "Finland"},
    {"value": "PL", "label": "Poland"},
    {"value": "CZ", "label": "Czech Republic"},
    {"value": "HU", "label": "Hungary"},
    {"value": "RO", "label": "Romania"},
    {"value": "GR", "label": "Greece"},
    {"value": "PT", "label": "Portugal"},
    {"value": "JP", "label": "Japan"},
    {"value": "CN", "label": "China"},
    {"value": "IN", "label": "India"},
    {"value": "KR", "label": "South Korea"},
    {"value": "SG", "label": "Singapore"},
    {"value": "AU", "label": "Australia"},
    {"value": "NZ", "label": "New Zealand"},
    {"value": "BR", "label": "Brazil"},
    {"value": "AR", "label": "Argentina"},
    {"value": "ZA", "label": "South Africa"},
]

CANADIAN_PROVINCE_OPTIONS: List[Option] = [
    {"value": "AB", "label": "Alberta"},
    {"value": "BC", "label": "British Columbia"},
    {"value": "MB", "label": "Manitoba"},
    {"value": "NB", "label": "New Brunswick"},
    {"value": "NL", "label": "Newfoundland and Labrador"},
    {"value": "NS", "label": "Nova Scotia"},
    {"value": "NT", "label": "Northwest Territories"},
    {"value": "NU", "label": "Nunavut"},
    {"value": "ON", "label": "Ontario"},
    {"value": "PE", "label": "Prince Edward Island"},
    {"value": "QC", "label": "Quebec"},
    {"value": "SK", "label": "Saskatchewan"},
    {"value": "YT", "label": "Yukon"},
]

IDENTITY_DOCUMENT_TYPES: List[Dict[str, object]] = [
    {
        "value": GuardDocumentType.DRIVERS_LICENSE.value,
        "label": "Driver's License (Provincial)",
        "requiresProvince": True,
        "requiresExpiry": True,
        "mandatory": False,
    },
    {
        "value": GuardDocumentType.PROVINCIAL_ID.value,
        "label": "Provincial Photo ID Card",
        "requiresProvince": True,
        "requiresExpiry": True,
        "mandatory": False,
    },
    {
        "value": GuardDocumentType.CANADIAN_PASSPORT.value,
        "label": "Canadian Passport",
        "requiresProvince": False,
        "requiresExpiry": True,
        "mandatory": False,
    },
    {
        "value": GuardDocumentType.PR_CARD.value,
        "label": "Permanent Resident (PR) Card",
        "requiresProvince": False,
        "requiresExpiry": True,
        "mandatory": False,
    },
    {
        "value": GuardDocumentType.WORK_PERMIT.value,
        "label": "Work Permit (Photo Version)",
        "requiresProvince": False,
        "requiresExpiry": True,
        "mandatory": False,
    },
    {
        "value": GuardDocumentType.STUDY_PERMIT.value,
        "label": "Study Permit (Photo Version)",
        "requiresProvince": False,
        "requiresExpiry": True,
        "mandatory": False,
    },
]

SECURITY_LICENSE_TYPE_OPTIONS: List[Option] = [
    {"value": SecurityLicenseType.SECURITY_GUARD.value, "label": "Security Guard"},
    {"value": SecurityLicenseType.PRIVATE_INVESTIGATOR.value, "label": "Private Investigator"},
    {"value": SecurityLicenseType.DUAL_SECURITY_GUARD_PRIVATE_INVESTIGATOR.value,
     "label": "Dual (Security Guard + Private Investigator)"},
]

TRAINING_CERTIFICATE_TYPE_OPTIONS: List[Option] = [
    {"value": TrainingCertificateType.BASIC_SECURITY_TRAINING.value, "label": "Basic Security Training (BST)"},
    {"value": TrainingCertificateType.STANDARD_FIRST_AID_CPR_AED.value, "label": "Standard First Aid & CPR-C/AED"},
    {"value": TrainingCertificateType.USE_OF_FORCE_DEFENSIVE_TACTICS.value,
     "label": "Use of Force / Defensive Tactics"},
    {"value": TrainingCertificateType.DE_ESCALATION_CONFLICT_MANAGEMENT.value,
     "label": "De-escalation / Conflict Management"},
    {"value": TrainingCertificateType.WHMIS.value, "label": "WHMIS"},
    {"value": TrainingCertificateType.BATON_HANDCUFF_TRAINING.value, "label": "Baton / Handcuff Training"},
]

POLICE_CLEARANCE_AUTHORITY_TYPE_OPTIONS: List[Option] = [
    {"value": PoliceClearanceAuthorityType.MUNICIPAL_POLICE_SERVICE.value, "label": "Municipal Police Service"},
    {"value": PoliceClearanceAuthorityType.PROVINCIAL_POLICE_SERVICE.value, "label": "Provincial Police Service"},
    {"value": PoliceClearanceAuthorityType.RCMP.value, "label": "RCMP"},
    {"value": PoliceClearanceAuthorityType.RCMP_ACCREDITED_PROVIDER.value, "label": "RCMP-accredited provider"},
    {"value": PoliceClearanceAuthorityType.FIRST_NATIONS_POLICE_SERVICE.value, "label": "First Nations Police Service"},
    {"value": PoliceClearanceAuthorityType.OTHER.value, "label": "Other (Specify)"},
]

TRAINING_ISSUER_OPTIONS_MAP: Dict[str, List[Option]] = {
    TrainingCertificateType.BASIC_SECURITY_TRAINING.value: [
        {"value": TrainingIssuerType.PROVINCIAL_APPROVED_TRAINING_PROVIDER.value,
         "label": "Provincial approved training provider"},
        {"value": TrainingIssuerType.PRIVATE_SECURITY_ACADEMY_APPROVED.value,
         "label": "Private security academy (approved)"},
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
    TrainingCertificateType.STANDARD_FIRST_AID_CPR_AED.value: [
        {"value": TrainingIssuerType.ST_JOHN_AMBULANCE.value, "label": "St. John Ambulance"},
        {"value": TrainingIssuerType.PROVINCIAL_APPROVED_TRAINING_PROVIDER.value,
         "label": "Provincial approved training provider"},
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
    TrainingCertificateType.USE_OF_FORCE_DEFENSIVE_TACTICS.value: [
        {"value": TrainingIssuerType.PRIVATE_SECURITY_ACADEMY_APPROVED.value,
         "label": "Private security academy (approved)"},
        {"value": TrainingIssuerType.TRAINING_PROVIDER_ACCREDITED.value,
         "label": "Training provider (accredited)"},
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
    TrainingCertificateType.DE_ESCALATION_CONFLICT_MANAGEMENT.value: [
        {"value": TrainingIssuerType.PRIVATE_SECURITY_ACADEMY_APPROVED.value,
         "label": "Private security academy (approved)"},
        {"value": TrainingIssuerType.TRAINING_PROVIDER_ACCREDITED.value,
         "label": "Training provider (accredited)"},
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
    TrainingCertificateType.WHMIS.value: [
        {"value": TrainingIssuerType.WORKPLACE_APPROVED_TRAINING_PROVIDER.value,
         "label": "Workplace-approved training provider"},
        {"value": TrainingIssuerType.TRAINING_PROVIDER_ACCREDITED.value,
         "label": "Training provider (accredited)"},
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
    TrainingCertificateType.BATON_HANDCUFF_TRAINING.value: [
        {"value": TrainingIssuerType.PRIVATE_SECURITY_ACADEMY_APPROVED.value,
         "label": "Private security academy (approved)"},
        {"value": TrainingIssuerType.TRAINING_PROVIDER_ACCREDITED.value,
         "label": "Training provider (accredited)"},
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
    TrainingCertificateType.OTHER.value: [
        {"value": TrainingIssuerType.OTHER.value, "label": "Other (Specify)"},
    ],
}

CLIENT_SITE_TYPE_OPTIONS: List[Option] = [
    {"value": ClientSiteType.OFFICE.value, "label": "Office"},
    {"value": ClientSiteType.WAREHOUSE.value, "label": "Warehouse"},
    {"value": ClientSiteType.EVENT.value, "label": "Event"},
    {"value": ClientSiteType.RESIDENTIAL.value, "label": "Residential"},
]

CLIENT_BILLING_MODEL_OPTIONS: List[Option] = [
    {"value": "per_hour", "label": "Per Hour"},
    {"value": "per_shift", "label": "Per Shift"},
]

CLIENT_SUBSCRIPTION_TIER_OPTIONS: List[Option] = [
    {"value": "basic", "label": "Basic"},
    {"value": "standard", "label": "Standard"},
    {"value": "premium", "label": "Premium"},
]

CLIENT_GUARD_TYPE_OPTIONS: List[Option] = [
    {"value": ClientGuardType.ARMED.value, "label": "Armed"},
    {"value": ClientGuardType.UNARMED.value, "label": "Un-Armed"},
    {"value": ClientGuardType.TACTICAL.value, "label": "Tactical"},
]

CLIENT_TYPE_OPTIONS: List[Option] = [
    {"value": ClientType.COMPANY.value, "label": "Company"},
    {"value": ClientType.INDIVIDUAL.value, "label": "Individual"},
]
