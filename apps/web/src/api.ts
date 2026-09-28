export type Dataset = { id: string; name: string; created_at: string }
export type Person = { id: string; dataset_id: string; display_name: string }
export type Trait = {
  id: string; dimension: string; key: string; statement: string; confidence: number;
  support_count: number; counter_count: number; first_seen: string | null;
  last_seen: string | null; status: string; context: Record<string, unknown>
}
export type Preview = {
  filename: string; sha256: string; message_count: number; person_candidates: string[];
  first_timestamp: string | null; last_timestamp: string | null; unknown_timestamp: number;
  errors: { locator: string; message: string }[]; warnings: { locator: string; message: string }[];
  error_count: number; warning_count: number
}
export type Claim = {
  id: string; person_id: string; dimension: string; name: string; statement: string;
  context: Record<string, unknown>; confidence: number; status: string;
  first_seen: string | null; last_seen: string | null;
  evidence: {
    id: string; relation: string; excerpt: string; event_id: string; timestamp: string | null;
    source_file: string; source_locator: string;
    context: { event_id: string; speaker: string; text: string; timestamp: string | null; is_evidence: boolean }[]
  }[]
}

const base = import.meta.env.VITE_API_BASE_URL ?? ''

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${base}/api${path}`, init)
  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json() as { detail?: string }
      if (body.detail) message = body.detail
    } catch { /* Preserve status when the response is not JSON. */ }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function jsonPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
}

export function displayDate(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : 'Unknown'
}
