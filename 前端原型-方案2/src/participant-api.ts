export type Assignment = { id: string; round_no: number; state: string; task_code?: 'A' | 'B'; task_title?: string; condition?: 'AI' | 'INDEPENDENT' }
type Identity = { study_code: string; consented: boolean; csrf_token: string }

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
}
