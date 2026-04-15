from __future__ import annotations

from datetime import date, datetime
from enum import Enum
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


class SourceStatus(str, Enum):
    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    NOT_FOUND = "not_found"


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
    source_statuses: list[SourceResult] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=datetime.utcnow)
