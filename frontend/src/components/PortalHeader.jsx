export default function PortalHeader({
  viewerRole,
  authUser,
  logoutAuth,
  portalPage,
  setPortalPage,
  health,
}) {
  return (
    <header className="topbar">
      <div>
        <h1>AGI CardioSense</h1>
        <p>
          {viewerRole === 'doctor'
            ? 'Doctor Dashboard - full clinical decision support'
            : 'Patient Dashboard - simplified care and precautions'}
        </p>
        <div className="role-switch">
          <button className={`btn ${viewerRole === 'doctor' ? 'primary' : ''}`} disabled>
            Doctor View
          </button>
          <button className={`btn ${viewerRole === 'patient' ? 'primary' : ''}`} disabled>
            Patient View
          </button>
          <span className="active-user">Logged in: <b>{authUser.name}</b> ({authUser.user_id})</span>
          <button className="btn" onClick={logoutAuth}>Logout</button>
        </div>
        <div className="page-switch">
          <button className={`btn ${portalPage === 'workspace' ? 'primary' : ''}`} onClick={() => setPortalPage('workspace')}>Workspace</button>
          <button className={`btn ${portalPage === 'diagnosis' ? 'primary' : ''}`} onClick={() => setPortalPage('diagnosis')}>Diagnosis</button>
          <button className={`btn ${portalPage === 'assistant' ? 'primary' : ''}`} onClick={() => setPortalPage('assistant')}>
            {viewerRole === 'doctor' ? 'Monitoring' : 'Assistant'}
          </button>
        </div>
      </div>
      <div className="status-grid">
        <div className="status-card"><span>System</span><strong>{health?.status === 'ok' ? 'Online' : 'Checking...'}</strong></div>
        <div className="status-card"><span>Model Accuracy</span><strong>{health ? `${health.accuracy}%` : '--'}</strong></div>
      </div>
    </header>
  )
}
