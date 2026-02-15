export default function PortalHeader({
  viewerRole,
  authUser,
  logoutAuth,
  portalPage,
  diagnosisStage,
  setPortalPage,
  health,
}) {
  const roleLabel = viewerRole === 'doctor' ? 'Doctor View' : 'Patient View'
  const subtitle = viewerRole === 'doctor'
    ? 'Clinical command center for high-confidence decision support'
    : 'Personal heart-care workspace with guided diagnosis and follow-up'

  return (
    <header className="topbar">
      <div className="topbar-main">
        <p className="topbar-kicker">AI Cardiovascular Suite</p>
        <h1>AGI CardioSense</h1>
        <p>{subtitle}</p>
        <div className="identity-strip">
          <span className="identity-chip">{roleLabel}</span>
          <span className="identity-chip">User: {authUser.user_id}</span>
          <span className="identity-chip">Name: {authUser.name}</span>
        </div>
        <div className="role-switch switch-row">
          <button className={`btn ${viewerRole === 'doctor' ? 'primary' : ''}`} disabled>Doctor</button>
          <button className={`btn ${viewerRole === 'patient' ? 'primary' : ''}`} disabled>Patient</button>
          <button className="btn" onClick={logoutAuth}>Logout</button>
        </div>
        <div className="page-switch switch-row">
          <button className={`btn ${portalPage === 'workspace' ? 'primary' : ''}`} onClick={() => setPortalPage('workspace')}>
            Profile
          </button>
          <button className={`btn ${portalPage === 'diagnosis' && diagnosisStage === 'inputs' ? 'primary' : ''}`} onClick={() => setPortalPage('inputs')}>
            Inputs
          </button>
          <button className={`btn ${portalPage === 'diagnosis' && diagnosisStage === 'diagnosis' ? 'primary' : ''}`} onClick={() => setPortalPage('diagnosis')}>
            Diagnosis
          </button>
          <button className={`btn ${portalPage === 'assistant' ? 'primary' : ''}`} onClick={() => setPortalPage('report')}>
            Report
          </button>
        </div>
      </div>
      <div className="status-grid">
        <div className="status-card"><span>System</span><strong>{health?.status === 'ok' ? 'Online' : 'Checking...'}</strong></div>
        <div className="status-card"><span>Model Accuracy</span><strong>{health ? `${health.accuracy}%` : '--'}</strong></div>
        <div className="status-card"><span>Current Page</span><strong>{portalPage === 'diagnosis' ? diagnosisStage : portalPage}</strong></div>
        <div className="status-card"><span>Session</span><strong>{viewerRole}</strong></div>
      </div>
    </header>
  )
}
