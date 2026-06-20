import { useState } from 'react'

import { useResumeStore } from '../../store/useResumeStore'

interface CompanySelectorProps {
  runId: string | null
}

const COMPANIES: Array<{ key: string; label: string }> = [
  { key: 'amazon', label: 'Amazon' },
  { key: 'google', label: 'Google' },
  { key: 'meta', label: 'Meta' },
  { key: 'microsoft', label: 'Microsoft' },
  { key: 'flipkart', label: 'Flipkart' },
  { key: 'swiggy', label: 'Swiggy' },
  { key: 'zomato', label: 'Zomato' },
  { key: 'razorpay', label: 'Razorpay' },
  { key: 'cred', label: 'CRED' },
  { key: 'meesho', label: 'Meesho' },
  { key: 'zepto', label: 'Zepto' },
  { key: 'phonepe', label: 'PhonePe' },
  { key: 'atlassian', label: 'Atlassian' },
  { key: 'stripe', label: 'Stripe' },
  { key: 'infosys', label: 'Infosys' },
]

const SENIORITY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: 'junior', label: 'Junior' },
  { value: 'mid', label: 'Mid' },
  { value: 'senior', label: 'Senior' },
  { value: 'staff', label: 'Staff / Lead' },
  { value: 'em', label: 'Engineering Manager' },
]

export default function CompanySelector({ runId }: CompanySelectorProps) {
  const fetchCompanyReadiness = useResumeStore((s) => s.fetchCompanyReadiness)
  const companyReadinessLoading = useResumeStore((s) => s.companyReadinessLoading)
  const companyReadinessError = useResumeStore((s) => s.companyReadinessError)

  const [companyKey, setCompanyKey] = useState('flipkart')
  const [seniority, setSeniority] = useState('mid')
  const [localError, setLocalError] = useState<string | null>(null)

  const handleSubmit = () => {
    setLocalError(null)
    if (!runId) {
      setLocalError('Please run an analysis first.')
      return
    }
    void fetchCompanyReadiness(runId, companyKey, seniority)
  }

  const errorMessage = localError ?? companyReadinessError

  return (
    <div
      style={{
        background: '#ffffff',
        border: '1.5px solid #e2e2ef',
        borderRadius: '16px',
        padding: '20px 24px',
        maxWidth: '1200px',
        margin: '20px auto 0',
      }}
    >
      <div style={{ fontSize: '14px', fontWeight: 700, color: '#0d0d1a', marginBottom: '4px' }}>
        Check readiness for a specific company
      </div>
      <div style={{ fontSize: '13px', color: '#8888aa', marginBottom: '16px' }}>
        No JD? Select a company to check how ready your resume is.
      </div>

      <div
        style={{
          display: 'flex',
          flexDirection: 'row',
          gap: '12px',
          flexWrap: 'wrap',
          marginBottom: '16px',
        }}
      >
        <select
          value={companyKey}
          onChange={(event) => setCompanyKey(event.target.value)}
          style={{
            flex: 1,
            minWidth: '160px',
            border: '1.5px solid #e2e2ef',
            borderRadius: '8px',
            padding: '9px 12px',
            fontSize: '14px',
            background: '#ffffff',
            color: '#0d0d1a',
            fontFamily: 'inherit',
          }}
        >
          {COMPANIES.map((company) => (
            <option key={company.key} value={company.key}>
              {company.label}
            </option>
          ))}
        </select>
        <select
          value={seniority}
          onChange={(event) => setSeniority(event.target.value)}
          style={{
            flex: 1,
            minWidth: '160px',
            border: '1.5px solid #e2e2ef',
            borderRadius: '8px',
            padding: '9px 12px',
            fontSize: '14px',
            background: '#ffffff',
            color: '#0d0d1a',
            fontFamily: 'inherit',
          }}
        >
          {SENIORITY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={companyReadinessLoading}
        style={{
          fontFamily: 'inherit',
          background: companyReadinessLoading ? '#c8c8e0' : '#5b5fc7',
          color: companyReadinessLoading ? '#8888aa' : '#ffffff',
          borderRadius: '8px',
          padding: '10px 20px',
          fontSize: '14px',
          fontWeight: 700,
          boxShadow: companyReadinessLoading ? 'none' : '0 4px 0 #3a3d9a',
          border: 'none',
          cursor: companyReadinessLoading ? 'not-allowed' : 'pointer',
        }}
      >
        {companyReadinessLoading ? 'Checking...' : 'Check Readiness →'}
      </button>

      {errorMessage && (
        <div style={{ color: '#dc2626', fontSize: '13px', marginTop: '12px' }}>
          {errorMessage}
        </div>
      )}
    </div>
  )
}
