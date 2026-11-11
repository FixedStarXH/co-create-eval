export type Assignment = { id: string; round_no: number; state: string; task_code?: 'A' | 'B'; task_title?: string; condition?: 'AI' | 'INDEPENDENT' }
type Identity = { study_code: string; consented: boolean; csrf_token: string }
export type DraftContent = Record<'goal' | 'student' | 'flow' | 'resource' | 'assessment', string>
export type Progress = { id: string; state: 'CREATED' | 'IDEATION' | 'DEVELOPMENT' | 'SUBMITTED' | 'EXPIRED'; server_time: string; ideation_deadline_at: string | null; idea_submitted_at: string | null; development_deadline_at: string | null; idea: { values: string[]; revision: number; saved_at: string | null } | null; draft: { sections: Partial<DraftContent>; revision: number; saved_at: string | null } | null }
type SaveResult = { revision: number; saved_at: string }
export type ChatRequest = { id: string; client_request_id: string; message: string; reply: string | null; status: 'PENDING' | 'SUCCEEDED' | 'FAILED'; error_code: string | null; created_at: string; completed_at: string | null }

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch('/api/v1' + path, { credentials: 'same-origin', ...options })
  } catch {
    throw new Error('无法连接服务，请检查后端是否运行。')
  }
  const result = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '请求失败，请稍后重试。')
  return result.data as T
}

export const participantApi = {
  login: (study_code: string, credential: string) => request<Identity>('/auth/participant-login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ study_code, credential }) }),
  me: () => request<Identity>('/auth/me'),
  consent: (csrf: string) => request<{ consented_at: string }>('/participant/consent', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ consent_version: 'demo-1', agreed: true }) }),
  sessions: () => request<Assignment[]>('/participant/sessions'),
  logout: (csrf: string) => request<{ logged_out: boolean }>('/auth/logout', { method: 'POST', headers: { 'X-CSRF-Token': csrf } }),
  progress: (id: string) => request<Progress>(`/sessions/${encodeURIComponent(id)}/progress`),
  start: (id: string, csrf: string) => request<Progress>(`/sessions/${encodeURIComponent(id)}/start`, { method: 'POST', headers: { 'X-CSRF-Token': csrf } }),
  saveIdea: (id: string, csrf: string, expected_revision: number, values: string[]) => request<SaveResult>(`/sessions/${encodeURIComponent(id)}/idea-draft`, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ expected_revision, values }) }),
  submitIdea: (id: string, csrf: string, expected_revision: number) => request<Progress>(`/sessions/${encodeURIComponent(id)}/initial`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ expected_revision }) }),
  saveDraft: (id: string, csrf: string, expected_revision: number, sections: DraftContent) => request<SaveResult>(`/sessions/${encodeURIComponent(id)}/draft`, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ expected_revision, sections }) }),
  submit: (id: string, csrf: string, expected_revision: number) => request<{ id: string; submitted_at: string }>(`/sessions/${encodeURIComponent(id)}/submit`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ expected_revision }) }),
  chatHistory: (id: string) => request<ChatRequest[]>(`/sessions/${encodeURIComponent(id)}/chat`),
  sendChat: (id: string, csrf: string, client_request_id: string, message: string) => request<ChatRequest>(`/sessions/${encodeURIComponent(id)}/chat`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ client_request_id, message }) }),
}
