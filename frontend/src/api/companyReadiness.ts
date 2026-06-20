import { IS_MOCK } from '../hooks/useMockData'
import { mockCompanyReadiness } from '../mocks/mockReadinessData'
import type { CompanyReadinessResult } from '../types'

export async function fetchCompanyReadinessFromApi(
  token: string | undefined,
  runId: string,
  companyKey: string,
  seniorityOverride?: string,
): Promise<CompanyReadinessResult> {
  if (IS_MOCK) {
    await new Promise((r) => setTimeout(r, 400))
    const supported = ['amazon', 'flipkart', 'google', 'swiggy', 'razorpay']
    if (!supported.includes(companyKey)) {
      throw new Error('This company is not yet supported. More companies coming soon.')
    }
    return { ...mockCompanyReadiness, company_key: companyKey, company_display_name: companyKey }
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  const res = await fetch('/api/company-readiness', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      run_id: runId,
      company_key: companyKey,
      seniority_override: seniorityOverride ?? null,
    }),
  })
  if (!res.ok) {
    const err = (await res.json().catch(() => ({}))) as { detail?: string }
    throw new Error(err?.detail || `Company readiness fetch failed: ${res.status}`)
  }
  return res.json() as Promise<CompanyReadinessResult>
}
