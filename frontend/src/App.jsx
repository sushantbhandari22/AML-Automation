import { useState, useRef, useCallback, useEffect } from 'react'
import bankLogo from './assets/bankLogo.png'
import './App.css'

// const API = 'http://localhost:8000'
const API = `http://${window.location.hostname}:8000`

const STAGES = [
  { id: 1, label: 'Ingest' },
  { id: 2, label: 'Verify' },
  { id: 3, label: 'Configure' },
  { id: 4, label: 'Finalize' },
]

const ANNEX_OPTIONS = [
  { key: 'I',       label: 'Annex I — Statement' },
  { key: 'II',      label: 'Annex II — Yearwise' },
  { key: 'III',     label: 'Annex III — Top 10 Deposits' },
  { key: 'IV',      label: 'Annex IV — Top 10 Withdrawals' },
  { key: 'TreeMap', label: 'Transaction Tree Map' },
]

function getChannelClass(name) {
  const n = name.toLowerCase()
  if (n.includes('esewa')) return 'esewa'
  if (n.includes('fonepay') || n.includes('fpay')) return 'fonepay'
  if (n.includes('connect') || n.includes('cip')) return 'cips'
  if (n.includes('mobile')) return 'mobile'
  return 'other'
}

// ── SVG Icons ────────────────────────────────
const UploadSVG = () => (
  <svg width="52" height="52" viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="52" height="52" rx="14" fill="#F1F5F9"/>
    <path d="M26 34V24M26 24L22 28M26 24L30 28" stroke="#64748B" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M20 36H32" stroke="#94A3B8" strokeWidth="1.6" strokeLinecap="round"/>
    <path d="M18 30a6 6 0 0 1 .88-3.12M34 30a6 6 0 0 0-.88-3.12" stroke="#94A3B8" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)

const FileSVG = () => (
  <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
    <rect width="28" height="28" rx="7" fill="#F1F5F9"/>
    <path d="M10 9h5l4 4v8a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1V10a1 1 0 0 1 1-1z" stroke="#475569" strokeWidth="1.5" strokeLinejoin="round"/>
    <path d="M15 9v4h4" stroke="#475569" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M12 16h4M12 18.5h2" stroke="#94A3B8" strokeWidth="1.3" strokeLinecap="round"/>
  </svg>
)

export default function App() {
  const [stage, setStage] = useState(1)
  const [sessionId, setSessionId] = useState(null)
  const [uploadResult, setUploadResult] = useState(null)
  const [verifyResult, setVerifyResult] = useState(null)
  const [generateResult, setGenerateResult] = useState(null)

  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const [meta, setMeta] = useState({
    bank_name: '', branch_name: '', account_name: '', account_number: '',
    account_type: '', nature_of_account: '', currency: 'NPR',
    start_date: '', end_date: '',
  })
  const [selectedAnnexes, setSelectedAnnexes] = useState(['I', 'II', 'III', 'IV', 'TreeMap'])

  // ── Instant Lookup ──────────────────────────────────
  useEffect(() => {
    const acc = meta.account_number
    if (acc && acc.length >= 8) {
      const delay = setTimeout(async () => {
        try {
          const res = await fetch(`${API}/api/lookup/${acc}`)
          if (res.ok) {
            const data = await res.json()
            if (Object.keys(data).length > 0) {
              setMeta(prev => ({
                ...prev,
                bank_name: data['Bank Name'] || prev.bank_name,
                branch_name: data['Branch Name'] || prev.branch_name,
                account_name: data['Account Name'] || prev.account_name,
                account_type: data['Account Type'] || prev.account_type,
                nature_of_account: data['Nature of Account'] || prev.nature_of_account,
                currency: data['Currency'] || prev.currency,
              }))
            }
          }
        } catch (e) {
          console.error('Lookup failed', e)
        }
      }, 500)
      return () => clearTimeout(delay)
    }
  }, [meta.account_number])

  // ── Upload ───────────────────────────────────────────
  const handleUpload = useCallback(async (file) => {
    if (!file) return
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch(`${API}/api/upload`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setSessionId(data.session_id)
      setUploadResult(data)
      if (data.detected_metadata) {
        setMeta(prev => ({
          ...prev,
          bank_name: data.detected_metadata.bank_name || prev.bank_name,
          branch_name: data.detected_metadata.branch_name || prev.branch_name,
          account_name: data.detected_metadata.account_name || prev.account_name,
          account_number: data.detected_metadata.account_number || prev.account_number,
          account_type: data.detected_metadata.account_type || prev.account_type,
          nature_of_account: data.detected_metadata.nature_of_account || prev.nature_of_account,
          currency: data.detected_metadata.currency || prev.currency,
          start_date: data.detected_metadata.start_date || prev.start_date,
          end_date: data.detected_metadata.end_date || prev.end_date,
        }))
      }
      setStage(2)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const onDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer?.files?.[0]
    if (file) handleUpload(file)
  }, [handleUpload])

  const onFileSelect = (e) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
  }

  // ── Verify ───────────────────────────────────────────
  const handleVerify = async () => {
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('session_id', sessionId)
      const res = await fetch(`${API}/api/verify`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setVerifyResult(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // ── Generate ─────────────────────────────────────────
  const handleGenerate = async () => {
    setLoading(true)
    setError(null)
    try {
      const form = new FormData()
      form.append('session_id', sessionId)
      Object.entries(meta).forEach(([k, v]) => form.append(k, v))
      form.append('annexes', selectedAnnexes.join(','))
      const res = await fetch(`${API}/api/generate`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(await res.text())
      const data = await res.json()
      setGenerateResult(data)
      setStage(4)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleAnnex = (key) => {
    setSelectedAnnexes(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    )
  }

  const updateMeta = (key, val) => setMeta(prev => ({ ...prev, [key]: val }))

  // ── Stage 1: Ingest ─────────────────────────────────
  const renderUpload = () => (
    <div className="card slide-up">
      <div className="card-title">Smart Ingestion</div>
      <div className="card-subtitle">
        Drop your raw bank statement file. The system automatically detects the format and extracts metadata.
      </div>
      <div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <div className="upload-icon"><UploadSVG /></div>
        <div className="upload-text">
          {dragging ? 'Release to upload' : 'Click or drag file to upload'}
        </div>
        <div className="upload-hint">Supports .csv and .xlsx formats</div>
        <input
          ref={fileInputRef}
          type="file"
          className="upload-input"
          accept=".csv,.xlsx,.xls"
          onChange={onFileSelect}
        />
      </div>
      {loading && (
        <div className="status-msg info" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div className="spinner"></div> Analyzing file structure...
        </div>
      )}
      {error && <div className="status-msg error">⚠ {error}</div>}
    </div>
  )

  // ── Stage 2: Verify ──────────────────────────────────
  const renderVerify = () => (
    <div className="card slide-up">
      <div className="card-title">Verification & Reconciliation</div>
      <div className="card-subtitle">
        Data integrity checks confirm no transactions were lost or misclassified during ingestion.
        {uploadResult && (
          <span className="file-badge" style={{ marginLeft: 12 }}>
            ✓ {uploadResult.file_type === 'raw' ? 'Raw Data' : 'Processed'} — {uploadResult.row_count} rows
          </span>
        )}
      </div>

      {uploadResult && (
        <div className="status-msg success" style={{ marginBottom: 20 }}>
          {uploadResult.message}
        </div>
      )}

      {!verifyResult && (
        <div className="btn-group" style={{ justifyContent: 'flex-start' }}>
          <button className="btn btn-primary" onClick={handleVerify} disabled={loading}>
            {loading ? <><div className="spinner"></div> Running Checks...</> : 'Run Verification Checks'}
          </button>
        </div>
      )}

      {verifyResult && (
        <>
          <div className="checks-grid">
            {verifyResult.checks.map((check, i) => (
              <div className="check-card fade-in" key={i} style={{ animationDelay: `${i * 0.08}s` }}>
                <div className="check-header">
                  <div className="check-name">{check.name}</div>
                  <span className={`check-badge ${check.passed ? 'pass' : 'fail'}`}>
                    {check.passed ? 'PASS' : 'FAIL'}
                  </span>
                </div>
                <div className="check-detail">
                  {check.name === 'Row Count Integrity' && (
                    <>Raw: <span>{check.raw_rows}</span> → Working: <span>{check.working_rows}</span> (removed <span>{check.summary_rows_removed}</span> summary rows)</>
                  )}
                  {check.name === 'Credit Sum Integrity' && (
                    <>Raw: <span>NPR {check.raw_credit_sum?.toLocaleString()}</span> ≡ Working: <span>NPR {check.working_credit_sum?.toLocaleString()}</span></>
                  )}
                  {check.name === 'Debit Sum Integrity' && (
                    <>Raw: <span>NPR {check.raw_debit_sum?.toLocaleString()}</span> ≡ Working: <span>NPR {check.working_debit_sum?.toLocaleString()}</span></>
                  )}
                  {check.name === 'Channel Classification Coverage' && (
                    <>Coverage: <span>{check.coverage_pct}%</span> classified ({check.uncategorized_count} unclassified)</>
                  )}
                </div>
                {check.channel_breakdown && (
                  <div className="channel-breakdown">
                    {Object.entries(check.channel_breakdown)
                      .sort(([, a], [, b]) => b - a)
                      .map(([ch, count]) => {
                        const maxCount = Math.max(...Object.values(check.channel_breakdown))
                        return (
                          <div className="channel-bar-wrap" key={ch}>
                            <div className="channel-label">{ch}</div>
                            <div className="channel-bar">
                              <div
                                className={`channel-bar-fill ${getChannelClass(ch)}`}
                                style={{ width: `${(count / maxCount) * 100}%` }}
                              />
                            </div>
                            <div className="channel-count">{count}</div>
                          </div>
                        )
                      })}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div className={`overall-badge ${verifyResult.overall === 'PASS' ? 'pass' : 'fail'}`}>
              {verifyResult.overall === 'PASS' ? '✓' : '✗'} Overall: {verifyResult.overall}
            </div>
            <button className="btn btn-primary" onClick={() => setStage(3)}>
              Continue to Configuration →
            </button>
          </div>
        </>
      )}
    </div>
  )

  // ── Stage 3: Configure ───────────────────────────────
  const renderConfig = () => (
    <div className="card slide-up">
      <div className="card-title">Report Configuration</div>
      <div className="card-subtitle">
        Set account metadata and select which annexes to generate.
      </div>

      <div className="config-grid">
        <div className="form-group">
          <label>Bank Name</label>
          <input value={meta.bank_name} onChange={e => updateMeta('bank_name', e.target.value)} placeholder="e.g. Jyoti Bikash Bank" />
        </div>
        <div className="form-group">
          <label>Branch Name</label>
          <input value={meta.branch_name} onChange={e => updateMeta('branch_name', e.target.value)} placeholder="e.g. 064 (Parwanipur)" />
        </div>
        <div className="form-group">
          <label>Account Name</label>
          <input value={meta.account_name} onChange={e => updateMeta('account_name', e.target.value)} placeholder="e.g. Amir Husen Ansari" />
        </div>
        <div className="form-group">
          <label>Account Number</label>
          <input value={meta.account_number} onChange={e => updateMeta('account_number', e.target.value)} placeholder="e.g. 06401300927516" />
        </div>
        <div className="form-group">
          <label>Account Type</label>
          <input value={meta.account_type} onChange={e => updateMeta('account_type', e.target.value)} placeholder="e.g. 13" />
        </div>
        <div className="form-group">
          <label>Nature of Account</label>
          <input value={meta.nature_of_account} onChange={e => updateMeta('nature_of_account', e.target.value)} placeholder="e.g. Smart Savings" />
        </div>
        <div className="form-group">
          <label>Currency</label>
          <input value={meta.currency} onChange={e => updateMeta('currency', e.target.value)} />
        </div>
        <div className="form-group date-range-section">
          <div className="date-range-header">
            <span className="date-range-icon">📅</span>
            <div>
              <div className="date-range-title">Report Date Range <span style={{ color: '#ef4444', fontSize: 13 }}>*</span></div>
              <div className="date-range-hint">Both start and end dates are required to generate the report.</div>
            </div>
          </div>
          <div className="date-range-inputs">
            <div className="date-input-wrap">
              <label>Start Date</label>
              <input type="date" value={meta.start_date} onChange={e => updateMeta('start_date', e.target.value)} required />
            </div>
            <div className="date-range-divider">→</div>
            <div className="date-input-wrap">
              <label>End Date</label>
              <input type="date" value={meta.end_date} onChange={e => updateMeta('end_date', e.target.value)} required />
            </div>
          </div>
        </div>
      </div>

      <div style={{ marginBottom: 10 }}>
        <label style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Select Reports
        </label>
      </div>
      <div className="annex-checkboxes">
        {ANNEX_OPTIONS.map(opt => (
          <label key={opt.key} className={`annex-checkbox ${selectedAnnexes.includes(opt.key) ? 'selected' : ''}`}>
            <input type="checkbox" checked={selectedAnnexes.includes(opt.key)} onChange={() => toggleAnnex(opt.key)} />
            {opt.label}
          </label>
        ))}
      </div>

      {error && <div className="status-msg error" style={{ marginBottom: 16 }}>⚠ {error}</div>}

      <div className="btn-group">
        <button className="btn btn-secondary" onClick={() => setStage(2)}>← Back</button>
        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={loading || selectedAnnexes.length === 0}
        >
          {loading ? <><div className="spinner"></div> Generating...</> : 'Generate Reports'}
        </button>
      </div>
    </div>
  )

  // ── Stage 4: Finalize ────────────────────────────────
  const renderDownload = () => (
    <div className="card slide-up">
      <div className="card-title">Generated Reports</div>
      <div className="card-subtitle">
        All reports have been generated. Download individually or as a complete package.
      </div>

      {generateResult && (
        <>
          <div className="status-msg success" style={{ marginBottom: 24 }}>
            ✓ {generateResult.files?.length} reports generated successfully.
          </div>

          <div className="files-list">
            {generateResult.files?.map((fname) => (
              <div className="file-item fade-in" key={fname}>
                <div className="file-info">
                  <FileSVG />
                  <div>
                    <div className="file-name">{fname}</div>
                    <div className="file-type">
                      {fname.startsWith('Annex')
                        ? 'Consolidated AML Report (Annex I–IV + TreeMap)'
                        : 'Supporting Audit Data (Main, Working, Pivots)'}
                    </div>
                  </div>
                </div>
                <a
                  href={`${API}/api/download/${sessionId}/${fname}`}
                  className="btn btn-primary"
                  download
                  style={{ textDecoration: 'none' }}
                >
                  Download
                </a>
              </div>
            ))}
          </div>

          <div className="btn-group" style={{ marginTop: 24 }}>
            <button className="btn btn-secondary" onClick={() => {
              setStage(1); setSessionId(null); setUploadResult(null);
              setVerifyResult(null); setGenerateResult(null); setError(null)
            }}>
              Process Another Account
            </button>
          </div>
        </>
      )}
    </div>
  )

  return (
    <>
      {/* ── Glass Header ── */}
      <header className="app-header">
        <div className="logo">
          <img src={bankLogo} className="nav-logo" alt="Bank Logo" />
          <div className="logo-divider"></div>
          <div>
            <div className="logo-text">AML Report Engine</div>
            <div className="logo-sub">Anti-Money Laundering Automation</div>
          </div>
        </div>
        <div className="header-status">
          <span className="status-dot"></span>
          System Online
        </div>
      </header>

      {/* ── Progress Stepper ── */}
      <div className="steps-bar">
        {STAGES.map((s, i) => (
          <div key={s.id} style={{ display: 'flex', alignItems: 'center' }}>
            <div
              className={`step ${stage === s.id ? 'active' : ''} ${stage > s.id ? 'completed' : ''}`}
              onClick={() => { if (s.id < stage) setStage(s.id) }}
            >
              <div className="step-number">
                {stage > s.id ? '✓' : s.id}
              </div>
              <span className="step-label">{s.label}</span>
            </div>
            {i < STAGES.length - 1 && (
              <div className={`step-connector ${stage > s.id ? 'done' : ''}`} />
            )}
          </div>
        ))}
      </div>

      {/* ── Content ── */}
      <main className="main-content">
        {stage === 1 && renderUpload()}
        {stage === 2 && renderVerify()}
        {stage === 3 && renderConfig()}
        {stage === 4 && renderDownload()}
      </main>
    </>
  )
}
