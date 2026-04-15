export interface CompanyInfo {
  nif: string;
  name: string | null;
  entity_type: "company" | "individual" | "unknown";
  valid: boolean;
}

export interface Contract {
  id: string;
  object_description: string;
  contracting_entity: string;
  contracting_nif: string;
  suppliers: string[];
  supplier_nifs: string[];
  contract_price: number | null;
  signing_date: string;
  procedure_type: string;
  cpv_codes: string[];
  district: string;
  municipality: string;
  year: number | null;
}

export interface InsolvencyProceeding {
  court: string;
  process_number: string;
  date: string;
  description: string;
  action_type: string;
}

export interface DebtorRecord {
  nif: string;
  name: string;
  debt_bracket: string | null;
  debt_bracket_label: string;
  found: boolean;
}

export interface SourceResult {
  source: string;
  status: "ok" | "error" | "timeout" | "not_found";
  error: string | null;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface EntityReport {
  nif: string;
  company: CompanyInfo | null;
  contracts: Contract[];
  contracts_total_value: number;
  insolvency_proceedings: InsolvencyProceeding[];
  has_insolvency: boolean;
  debtor: DebtorRecord | null;
  is_tax_debtor: boolean;
  iberinform_content: string | null;
  source_statuses: SourceResult[];
  queried_at: string;
}
