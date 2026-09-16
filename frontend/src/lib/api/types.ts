/* Shapes of the Kayan backend responses the console consumes. */

export type TicketStatus = "open" | "in_progress" | "waiting_customer" | "replied" | "expired" | "closed";
export type Channel = "whatsapp" | "call" | "portal";

export type SlaInfo = { breached: boolean; remaining_ar?: string | null; remaining_seconds?: number | null };

export type CrmStats = {
  total: number;
  by_status: Partial<Record<TicketStatus, number>>;
  today: number;
  closure_rate_pct: number;
  avg_first_response_hours: number;
  sla_breached: number;
  by_channel: Partial<Record<Channel, number>>;
};

export type KanbanCard = {
  id: string;
  customer_name_ar: string | null;
  subject_ar: string | null;
  department_id?: string | null;
  department_ar: string | null;
  priority: "high" | "normal" | "low" | string;
  channel: Channel | string;
  sla_remaining_ar: string | null;
  last_update: string | null;
};

export type KanbanColumn = { status: TicketStatus; title_ar: string; count: number; cards: KanbanCard[] };
export type Kanban = { columns: KanbanColumn[] };

export type Department = { id: string; name_ar: string; sla_hours: number };

export type Ticket = {
  id: string;
  subject_ar: string | null;
  channel: Channel | string;
  phone: string | null;
  beneficiary_id: string | null;
  department_id: string | null;
  department_ar: string | null;
  priority: string;
  status: TicketStatus;
  status_ar: string;
  customer_name_ar: string | null;
  opened_at: string;
  updated_at: string | null;
  last_update?: string | null;
  sla: SlaInfo;
};

export type TicketMessage = {
  id: string;
  direction: "inbound" | "outbound";
  sender: "beneficiary" | "bot" | "agent" | string;
  sender_name?: string | null;
  body_ar: string;
  sent_at: string;
  is_internal?: boolean | number;
  status?: string | null;
};

export type TicketDetail = Ticket & {
  whatsapp_number: string | null;
  messages: TicketMessage[];
  previous_tickets: string[];
};

export type BeneficiaryRow = {
  id: string;
  file_no: string;
  name_ar: string;
  status: string;
  case_type: string;
  city: string | null;
  mobile: string | null;
  completion_pct: number;
  dependents: number;
};

export type Dependent = {
  id: string;
  name_ar: string;
  relationship: string | null;
  birth_date: string | null;
  gender: string | null;
  education: string | null;
  special_needs: number | boolean;
};

export type BeneficiaryHistory = {
  beneficiary: {
    id: string;
    file_no: string;
    status: string;
    case_type: string;
    orphan_category?: string | null;
    name_ar: string;
    category_ar: string | null;
    city: string | null;
    created_at: string | null;
    approved_at: string | null;
  };
  completeness: {
    pct: number;
    missing_fields: { field?: string; section?: string; section_id?: string; section_ar?: string }[];
    missing_documents: { document_type_id?: string; id?: string; name_ar: string }[];
  };
  household: { size: number; dependents: Dependent[] };
  financial: {
    monthly_income_sar: number | null;
    total_obligations_sar: number | null;
    total_person_costs_sar: number | null;
    per_capita_monthly_sar: number | null;
    need_score: number | null;
  };
  support_requests: {
    id: string;
    program_id?: string | null;
    program_ar: string | null;
    request_type_id?: string | null;
    title_ar: string | null;
    stage: string;
    requested_amount_sar: number | null;
    decision?: string | null;
    decision_ar: string | null;
    approved_amount_sar: number | null;
  }[];
  enrollments: { id: string; program_id?: string | null; program_ar?: string | null }[];
  disbursements: {
    count: number;
    paid_sar: number;
    upcoming_sar: number;
    rows: { id: string; enrollment_id: string | null; program_id?: string | null; amount: number; status: string; due_date: string }[];
  };
  payments: { count: number; total_sar: number };
  tickets: { id: string; subject_ar: string | null; status?: string; status_ar: string | null; channel: string; opened_at: string }[];
  channel_sessions: { calls: number; whatsapp: number };
};

export type SupportRequest = {
  id: string;
  beneficiary_id: string;
  program_id: string;
  request_type_id: string | null;
  title_ar: string | null;
  internal_classification: string | null;
  requested_amount_sar: number | null;
  stage: string;
  decision: string | null;
  name_ar: string | null;
  program_ar: string | null;
  decision_ar: string | null;
  approved_amount_sar: number | null;
};

export type Program = {
  id: string;
  name_ar: string;
  name_en?: string;
  description_ar: string;
  request_types_count: number;
};

export type RequestType = {
  id: string;
  program_id: string;
  name_ar: string;
  ceiling_sar: number | null;
  kind?: string;
  recurring?: boolean;
};

export type CommitteeItem = {
  support_request_id: string;
  beneficiary_id: string;
  name_ar: string | null;
  program_id?: string | null;
  program_ar: string | null;
  request_type_id?: string | null;
  title_ar: string | null;
  requested_amount_sar: number | null;
  need_score: number | null;
  per_capita_monthly_sar: number | null;
  household_size: number | null;
  recommendation_ar: string | null;
};

export type Disbursement = {
  id: string;
  beneficiary_id: string;
  program_id: string | null;
  enrollment_id: string | null;
  amount: number;
  status: string;
  due_date: string;
};

export type DisbursementRun = {
  window_days: number;
  count: number;
  total_sar: number;
  by_program_ar: Record<string, number>;
  disbursements: Disbursement[];
};

export type Overview = {
  beneficiaries: { total: number; by_status: Record<string, number>; dependents: number };
  support_requests: { total: number; by_stage: Record<string, number>; decisions: Record<string, number> };
  programs: Record<string, number>;
  payments_total_sar: number;
  sponsorships: { count: number; monthly_sar: number };
  channels: { tickets: number; calls: number; whatsapp_sessions: number };
};

export type Notification = {
  id: string;
  channel?: string;
  to?: string;
  body?: string;
  body_ar?: string;
  kind?: string;
  created_at?: string;
  sent_at?: string;
};

export type AgentContext = {
  known?: boolean;
  beneficiary_id?: string;
  file_no?: string;
  name_ar?: string;
  file_status?: string;
  completion_pct?: number;
  missing_documents?: string[];
  open_requests?: { id: string; title_ar?: string | null; stage: string }[];
  open_tickets?: string[];
  next_disbursement?: { amount: number; due_date: string } | null;
};

export type AgentChatResponse = { reply: string; context: AgentContext | null; known_beneficiary: boolean };

export type CaseStep = {
  step_id: string;
  name_ar?: string | null;
  scheduled_at?: string | null;
  status: "scheduled" | "completed" | string;
  assigned_staff_id?: string | null;
  findings_ar?: string | null;
  completed_at?: string | null;
};

export type CaseStudy = {
  id: string;
  status: "open" | "closed" | string;
  steps: CaseStep[];
  recommendation_ar: string | null;
  social_researcher_id: string | null;
  opened_at: string | null;
};

export type Decision = {
  decision: "accepted" | "docs_required" | "declined" | string;
  decision_ar?: string | null;
  approved_amount_sar: number | null;
  reason_ar: string | null;
  required_documents_ar: string[] | null;
  committee_date: string | null;
};

export type Enrollment = {
  id: string;
  type: "one_time" | "monthly_recurring" | string | null;
  monthly_amount: number | null;
  total_approved: number | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
};

export type SupportRequestDetail = SupportRequest & {
  case_description_ar: string | null;
  description_ar: string | null;
  channel: string | null;
  created_at: string | null;
  case_study: CaseStudy | null;
  decision: Decision | null;
  enrollment: Enrollment | null;
};

export type Staff = { id: string; name_ar: string; role_ar: string; department_id: string };
export type CaseStepRef = { id: string; name_ar: string; name_en?: string };

export type Permission =
  | "tickets:view"
  | "tickets:manage"
  | "beneficiaries:view"
  | "beneficiaries:manage"
  | "beneficiaries:review"
  | "requests:view"
  | "requests:create"
  | "casework:manage"
  | "committee:decide"
  | "finance:view"
  | "finance:manage"
  | "agent:test"
  | "staff:manage"
  | "admin:all";

export type SessionUser = {
  id: string;
  email: string | null;
  name_ar: string | null;
  name_en: string | null;
  role: string;
  department_id: string | null;
  staff_id: string | null;
  is_active: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
  created_at: string | null;
  extra_permissions: Permission[];
  revoked_permissions: Permission[];
  permissions: Permission[];
};

export type RoleInfo = { name_ar: string; name_en: string; permissions: Permission[] };
export type StaffUsersResponse = {
  count: number;
  users: SessionUser[];
  roles: Record<string, RoleInfo>;
  all_permissions: Permission[];
};
