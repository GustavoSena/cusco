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

export interface EntityProfile {
  nif: string;
  name: string;
  country: string | null;
  country_code: string | null;
  total_contracts: number | null;
  times_as_supplier: number | null;
  total_value_as_supplier: number | null;
  times_as_entity: number | null;
  total_value_as_entity: number | null;
}

export interface LEIRecord {
  lei: string;
  legal_name: string;
  other_names: string[];
  legal_address: string;
  legal_city: string;
  legal_region: string;
  legal_country: string;
  legal_postal_code: string;
  headquarters_address: string;
  headquarters_city: string;
  headquarters_country: string;
  registered_as: string;
  jurisdiction: string;
  entity_status: string;
  entity_category: string;
  legal_form_code: string;
  registration_status: string;
  initial_registration_date: string;
  last_update_date: string;
  next_renewal_date: string;
}

export interface SegSocialProcedure {
  code: string;
  title: string;
  variant: string;
  scope: string;
  procedure_type: string;
  career: string;
  service: string;
  publication_date: string;
  expiration_date: string;
  organism_id: string;
  organism_name: string;
  organism_acronym: string;
  documents: { title: string; url: string }[];
}

export interface SegSocialOrganism {
  id: string;
  name: string;
  acronym: string;
  procedure_count: number;
}

export interface AdCProcess {
  process_number: string;
  process_type: string;
  entities: string[];
  sector: string;
  practice_type: string;
  year_opened: string;
  year_decided: string;
  final_decision: string;
  status: string;
  title: string;
  court: string;
  court_process_number: string;
  origin_process: string;
  detail_url: string;
  pdf_url: string;
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
  entity_profile: EntityProfile | null;
  lei_record: LEIRecord | null;
  seg_social_procedures: SegSocialProcedure[];
  seg_social_organisms: SegSocialOrganism[];
  adc_processes: AdCProcess[];
  has_competition_issues: boolean;
  iberinform_content: string | null;
  source_statuses: SourceResult[];
  queried_at: string;
}

export interface NameSearchMatch {
  nif: string;
  name: string;
  source: string;
  lei?: string;
}

export interface NameSearchResult {
  query: string;
  results: NameSearchMatch[];
  total_matches: number;
}
