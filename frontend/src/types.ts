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

export interface PRRFunding {
  project_code: string;
  entity_name: string;
  role: string;
  cae_code: string;
  municipality: string;
  value_contracted: number | null;
  value_paid: number | null;
  reference_date: string;
}

export interface PRRContract {
  contract_code: string;
  description: string;
  entity_name: string;
  role: string;
  value: number | null;
  reference_date: string;
}

export interface PT2030Funding {
  operation_code: string;
  entity_name: string;
  role: string;
  beneficiary_percentage: number | null;
  value_contractualized: number | null;
  fund_approved: number | null;
  fund_executed: number | null;
  fund_paid: number | null;
  framework: string;
}

export interface GroupMember {
  nif: string;
  name: string;
  lei: string;
  country: string;
  entity_status: string;
  relationship: string;
}

export interface CorporateGroup {
  parent: GroupMember | null;
  children: GroupMember[];
  total_children: number;
  has_more_children: boolean;
}

export interface MunicipalityContract {
  nif: string;
  name: string;
  contract_count: number;
  total_value: number;
}

export interface CAECode {
  code: string;
  description: string;
  type: string; // "principal" | "secundario"
}

export interface PTDataSourceStatus {
  id: string;
  name: string;
  status: string;
  records: number | null;
}

export interface PTDataCompany {
  nif: string;
  name: string;
  sicae_name: string;
  address: string;
  type_code: string;
  vat_active: boolean;
  cae_codes: CAECode[];
  source_checks: PTDataSourceStatus[];
  public_contracts_total: number | null;
  public_contracts_value: number | null;
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
  status: "ok" | "error" | "timeout" | "not_found" | "pending";
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
  prr_fundings: PRRFunding[];
  prr_contracts: PRRContract[];
  has_prr_funding: boolean;
  prr_total_contracted: number;
  prr_total_paid: number;
  pt2030_fundings: PT2030Funding[];
  has_pt2030_funding: boolean;
  pt2030_total_fund_approved: number;
  pt2030_total_fund_paid: number;
  corporate_group: CorporateGroup | null;
  municipality_contracts: MunicipalityContract[];
  ptdata_company: PTDataCompany | null;
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
