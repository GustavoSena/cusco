from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class EntityType(str, Enum):
    COMPANY = "company"
    INDIVIDUAL = "individual"
    UNKNOWN = "unknown"


class CompanyInfo(BaseModel):
    nif: str
    name: str | None = None
    entity_type: EntityType = EntityType.UNKNOWN
    valid: bool = False


class Contract(BaseModel):
    id: str
    object_description: str = ""
    contracting_entity: str = ""
    contracting_nif: str = ""
    suppliers: list[str] = Field(default_factory=list)
    supplier_nifs: list[str] = Field(default_factory=list)
    contract_price: float | None = None
    signing_date: str = ""
    procedure_type: str = ""
    cpv_codes: list[str] = Field(default_factory=list)
    district: str = ""
    municipality: str = ""
    year: int | None = None


class InsolvencyProceeding(BaseModel):
    court: str = ""
    process_number: str = ""
    date: str = ""
    description: str = ""
    action_type: str = ""


class DebtBracket(str, Enum):
    C1 = "10000-50000"
    C2 = "50000-100000"
    C3 = "100000-250000"
    C4 = "250000-500000"
    C5 = "500000-1000000"
    C6 = "1000000+"


BRACKET_LABELS: dict[DebtBracket, str] = {
    DebtBracket.C1: "10.000 - 50.000",
    DebtBracket.C2: "50.000 - 100.000",
    DebtBracket.C3: "100.000 - 250.000",
    DebtBracket.C4: "250.000 - 500.000",
    DebtBracket.C5: "500.000 - 1.000.000",
    DebtBracket.C6: "> 1.000.000",
}


class DebtorRecord(BaseModel):
    nif: str
    name: str = ""
    debt_bracket: DebtBracket | None = None
    debt_bracket_label: str = ""
    found: bool = False


class EntityProfile(BaseModel):
    """Entity profile from IMPIC entity registry (dados.gov.pt)."""

    nif: str
    name: str = ""
    country: str | None = None
    country_code: str | None = None
    total_contracts: int | None = None
    times_as_supplier: int | None = None
    total_value_as_supplier: float | None = None
    times_as_entity: int | None = None
    total_value_as_entity: float | None = None


class LEIRecord(BaseModel):
    """Legal Entity Identifier record from GLEIF."""

    lei: str = ""
    legal_name: str = ""
    other_names: list[str] = Field(default_factory=list)
    legal_address: str = ""
    legal_city: str = ""
    legal_region: str = ""
    legal_country: str = ""
    legal_postal_code: str = ""
    headquarters_address: str = ""
    headquarters_city: str = ""
    headquarters_country: str = ""
    registered_as: str = ""
    jurisdiction: str = ""
    entity_status: str = ""
    entity_category: str = ""
    legal_form_code: str = ""
    registration_status: str = ""
    initial_registration_date: str = ""
    last_update_date: str = ""
    next_renewal_date: str = ""


class SegSocialProcedure(BaseModel):
    """Public recruitment/mobility procedure from Segurança Social."""

    code: str = ""
    title: str = ""
    variant: str = ""
    scope: str = ""  # INTERNAL / EXTERNAL
    procedure_type: str = ""  # COMMON, etc.
    career: str = ""
    service: str = ""  # region/service area
    publication_date: str = ""
    expiration_date: str = ""
    organism_id: str = ""
    organism_name: str = ""
    organism_acronym: str = ""
    documents: list[dict] = Field(default_factory=list)


class SegSocialOrganism(BaseModel):
    """Public organism from Segurança Social procedures."""

    id: str = ""
    name: str = ""
    acronym: str = ""
    procedure_count: int = 0


class AdCProcess(BaseModel):
    """Competition authority (AdC) process record."""

    process_number: str = ""
    process_type: str = ""  # praticas_anticoncorrenciais, concentracoes, contencioso, estudos_pareceres
    entities: list[str] = Field(default_factory=list)
    sector: str = ""
    practice_type: str = ""  # Abuso de Posição Dominante, Acordo Horizontal, etc.
    year_opened: str = ""
    year_decided: str = ""
    final_decision: str = ""  # Condenatória, Arquivamento, etc.
    status: str = ""  # Fechado, A decorrer, etc.
    title: str = ""  # For estudos/pareceres
    court: str = ""  # For contencioso
    court_process_number: str = ""  # For contencioso
    origin_process: str = ""  # For contencioso — links to PRC/CCENT
    detail_url: str = ""
    pdf_url: str = ""


class PRRFunding(BaseModel):
    """PRR (Plano de Recuperação e Resiliência) funding record for an entity."""

    project_code: str = ""
    entity_name: str = ""
    role: str = ""  # Beneficiário Final, Intermediário, etc.
    cae_code: str = ""
    municipality: str = ""
    value_contracted: float | None = None
    value_paid: float | None = None
    reference_date: str = ""


class PRRContract(BaseModel):
    """PRR public contract entry."""

    contract_code: str = ""
    description: str = ""
    entity_name: str = ""
    role: str = ""  # Adjudicante, Adjudicatário
    value: float | None = None
    reference_date: str = ""


class PT2030Funding(BaseModel):
    """Portugal 2030 programme funding record for an entity."""

    operation_code: str = ""
    entity_name: str = ""
    role: str = ""
    beneficiary_percentage: float | None = None
    value_contractualized: float | None = None
    fund_approved: float | None = None
    fund_executed: float | None = None
    fund_paid: float | None = None
    framework: str = ""


class GroupMember(BaseModel):
    """A member (parent or child) in a corporate group."""

    nif: str = ""
    name: str = ""
    lei: str = ""
    country: str = ""
    entity_status: str = ""  # ACTIVE / INACTIVE
    relationship: str = ""  # parent | child


class CorporateGroup(BaseModel):
    """Corporate group membership derived from GLEIF parent/child relationships."""

    parent: GroupMember | None = None
    children: list[GroupMember] = Field(default_factory=list)
    total_children: int = 0  # full count from GLEIF even if truncated
    has_more_children: bool = False


class SourceStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"
    PENDING = "pending"


class SourceResult(BaseModel):
    source: str
    status: SourceStatus
    error: str | None = None


class EntityReport(BaseModel):
    """Aggregated report for a single entity across all sources."""

    nif: str
    company: CompanyInfo | None = None
    contracts: list[Contract] = Field(default_factory=list)
    contracts_total_value: float = 0.0
    insolvency_proceedings: list[InsolvencyProceeding] = Field(default_factory=list)
    has_insolvency: bool = False
    debtor: DebtorRecord | None = None
    is_tax_debtor: bool = False
    entity_profile: EntityProfile | None = None
    lei_record: LEIRecord | None = None
    seg_social_procedures: list[SegSocialProcedure] = Field(default_factory=list)
    seg_social_organisms: list[SegSocialOrganism] = Field(default_factory=list)
    adc_processes: list[AdCProcess] = Field(default_factory=list)
    has_competition_issues: bool = False
    iberinform_content: str | None = None
    prr_fundings: list[PRRFunding] = Field(default_factory=list)
    prr_contracts: list[PRRContract] = Field(default_factory=list)
    has_prr_funding: bool = False
    prr_total_contracted: float = 0.0
    prr_total_paid: float = 0.0
    pt2030_fundings: list[PT2030Funding] = Field(default_factory=list)
    has_pt2030_funding: bool = False
    pt2030_total_fund_approved: float = 0.0
    pt2030_total_fund_paid: float = 0.0
    corporate_group: CorporateGroup | None = None
    source_statuses: list[SourceResult] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)
    report: EntityReport
