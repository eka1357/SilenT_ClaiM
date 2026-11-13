export type IntegrationMode = "live" | "replay" | "simulated" | "down";

export interface IntegrationStatusItem {
  mode: IntegrationMode;
  live: boolean;
  replay: boolean;
  label: string;
}

export interface HealthResponse {
  status: string;
  demo_mode: boolean;
  demo_offline: boolean;
  payback_enabled: boolean;
  paytm_mode: string;
  integrations: Record<string, IntegrationStatusItem | IntegrationMode>;
}

export interface HourlyPoint {
  ts_hour: string;
  n_payments: number;
  amount_paise: number;
}

export interface ShopDetectionView {
  id: string;
  day: string;
  baseline_paise: number;
  day_income_paise: number;
  dropped: boolean;
  eligible: boolean;
  quorum_share: number;
  rain_mm: number;
  rain_source: string;
  decision: "file" | "ask" | "none";
  reason: string;
  rules_version: string;
}

export interface ShopAskView {
  id: string;
  ask_kind: "consent" | "voice";
  status: "pending" | "answered" | "closed" | "human_review" | "declined";
  prompt_text_ta: string;
  has_audio: boolean;
  reply_type: string | null;
  transcript: string | null;
  cause_label: string | null;
  confidence: number | null;
  simulated_label: string | null;
  answered_at: string | null;
}

export interface ShopRefundView {
  id: string;
  refund_id: string;
  amount_paise: number;
  status: string;
  label: string;
}

export interface ShopClaimView {
  id: string;
  status: string;
  batch_id: string | null;
  consent_at: string | null;
  evidence_url: string;
  refund: ShopRefundView | null;
}

export interface ShopView {
  shop_id: string;
  name: string;
  owner: string;
  category: string;
  lat: number;
  lon: number;
  plan_active: boolean;
  status: "trading" | "quiet" | "dropped";
  baseline_paise: number;
  today_income_paise: number;
  hourly: HourlyPoint[];
  detection: ShopDetectionView | null;
  ask: ShopAskView | null;
  claim: ShopClaimView | null;
}

export interface StreetInfo {
  id: string;
  name: string;
  lat: number;
  lon: number;
}

export interface ScenarioClockView {
  running: boolean;
  active_day: string | null;
  current_hour: string | null;
  speed: number;
  hours_completed: number;
}

export interface StreetResponse {
  street: StreetInfo;
  clock: ScenarioClockView;
  shops: ShopView[];
}

export interface BatchClaimItem {
  id: string;
  shop_id: string;
  shop_name: string;
  owner: string;
  detection_id: string;
  batch_id: string | null;
  day: string | null;
  baseline_paise: number;
  day_income_paise: number;
  quorum_share: number;
  rain_mm: number;
  rain_source: string;
  rules_version: string;
  status: string;
  summary_text: string;
  consent_at: string | null;
  simulated_label: string | null;
  cause_label: string | null;
  evidence_url: string;
  refund: {
    id: string;
    refund_id: string;
    paytm_order_id: string | null;
    refund_month: string;
    amount_paise: number;
    status: string;
    label: string;
  } | null;
}

export interface BatchInfo {
  id: string;
  status: "open" | "pending" | "approved";
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  claims_count: number;
  claims: BatchClaimItem[];
}

export interface CurrentBatchResponse {
  batch: BatchInfo | null;
  id: string | null;
  status: string | null;
  claims: BatchClaimItem[];
}

export interface RefundMetricItem {
  claim_id: string;
  shop_id: string;
  refund_id: string;
  amount_paise: number;
  status: string;
  label: string;
}

export interface EvalMetrics {
  label: string;
  rules_version: string;
  split: string;
  total_cases: number;
  claims_filed: number;
  claims_right: number;
  wrong_claims: number;
  wrong_claim_share: number;
  false_positive_rate: number;
  closures_missed: number;
  total_closures: number;
  missed_claim_rate: number;
}

export interface MetricsResponse {
  forms_filled: number;
  taps: number;
  merchant_taps: number;
  adjuster_taps: number;
  claims_filed_in_run: number;
  avg_time_to_file_seconds: number;
  max_time_to_file_seconds: number;
  time_to_file_by_claim: Array<{
    claim_id: string;
    shop_id: string;
    decision_at: string | null;
    filed_at: string | null;
    seconds: number;
  }>;
  refunds: {
    count: number;
    total_amount_paise: number;
    payback_enabled: boolean;
    items: RefundMetricItem[];
  };
  eval: EvalMetrics;
  integrations: Record<string, IntegrationStatusItem | IntegrationMode>;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errBody = (await response.json()) as { detail?: string };
      if (errBody.detail) {
        detail = errBody.detail;
      }
    } catch {
      // Fallback to HTTP status
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function getHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>("/api/health");
}

export async function getStreet(
  streetId = "panagal_park_road",
  day?: string
): Promise<StreetResponse> {
  const query = day ? `?day=${encodeURIComponent(day)}` : "";
  return fetchJson<StreetResponse>(`/api/street/${encodeURIComponent(streetId)}${query}`);
}

export async function getCurrentBatch(): Promise<CurrentBatchResponse> {
  return fetchJson<CurrentBatchResponse>("/api/batches/current");
}

export async function getMetrics(): Promise<MetricsResponse> {
  return fetchJson<MetricsResponse>("/api/metrics");
}

export async function resetScenario(): Promise<{ status: string }> {
  return fetchJson<{ status: string }>("/api/scenario/reset", {
    method: "POST",
  });
}

export async function runScenario(
  day = "2026-10-21",
  speed = 60
): Promise<{ status: string; day: string; speed: number }> {
  return fetchJson<{ status: string; day: string; speed: number }>(
    "/api/scenario/run",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ day, speed }),
    }
  );
}

export async function submitConsent(
  askId: string,
  consent: boolean
): Promise<Record<string, unknown>> {
  const action = consent ? "consent" : "decline";
  return fetchJson<Record<string, unknown>>(
    `/api/asks/${encodeURIComponent(askId)}/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ consent }),
    }
  );
}

export async function submitVoice(
  askId: string,
  audioBlob: Blob,
  filename = "reply.wav"
): Promise<Record<string, unknown>> {
  const formData = new FormData();
  formData.append("file", audioBlob, filename);
  return fetchJson<Record<string, unknown>>(
    `/api/asks/${encodeURIComponent(askId)}/voice`,
    {
      method: "POST",
      body: formData,
    }
  );
}

export async function approveBatch(
  batchId: string
): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(
    `/api/batches/${encodeURIComponent(batchId)}/approve`,
    {
      method: "POST",
    }
  );
}

