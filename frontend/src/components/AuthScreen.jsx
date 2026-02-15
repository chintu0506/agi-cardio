export default function AuthScreen({
  health,
  error,
  authMode,
  authStage,
  authForm,
  setAuthForm,
  authLoading,
  otpCode,
  setOtpCode,
  switchAuthMode,
  signUp,
  login,
  verifyOtp,
  resendOtp,
  setAuthStage,
}) {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>AGI CardioSense</h1>
          <p>Secure Doctor and Patient access</p>
        </div>
        <div className="status-grid">
          <div className="status-card"><span>System</span><strong>{health?.status === 'ok' ? 'Online' : 'Checking...'}</strong></div>
          <div className="status-card"><span>Model Accuracy</span><strong>{health ? `${health.accuracy}%` : '--'}</strong></div>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}

      <section className="panel">
        <h2>{authMode === 'login' ? 'Login' : 'Sign Up'}</h2>
        <p className="muted">Signup uses OTP verification. Login uses password authentication.</p>
        <div className="actions">
          <button type="button" className={`btn ${authMode === 'login' ? 'primary' : ''}`} onClick={() => switchAuthMode('login')}>Login</button>
          <button type="button" className={`btn ${authMode === 'signup' ? 'primary' : ''}`} onClick={() => switchAuthMode('signup')}>Sign Up</button>
        </div>
        {authStage === 'credentials' ? (
          <>
            {authMode === 'signup' ? (
              <div className="profile-create-grid">
                <label><span>Full Name</span><input value={authForm.name} onChange={(e) => setAuthForm((p) => ({ ...p, name: e.target.value }))} /></label>
                <label><span>Email</span><input value={authForm.email} onChange={(e) => setAuthForm((p) => ({ ...p, email: e.target.value }))} /></label>
                <label><span>Password</span><input type="password" autoComplete="new-password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} /></label>
                <label><span>Role</span>
                  <select value={authForm.role} onChange={(e) => setAuthForm((p) => ({ ...p, role: e.target.value }))}>
                    <option value="patient">Patient</option>
                    <option value="doctor">Doctor</option>
                  </select>
                </label>
              </div>
            ) : (
              <div className="profile-create-grid">
                <label><span>Email or Mobile</span><input value={authForm.login} onChange={(e) => setAuthForm((p) => ({ ...p, login: e.target.value }))} /></label>
                <label><span>Password</span><input type="password" autoComplete="current-password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} /></label>
              </div>
            )}
            <div className="actions">
              {authMode === 'signup' ? (
                <button type="button" className="btn primary" onClick={signUp} disabled={authLoading}>{authLoading ? 'Sending OTP...' : 'Send Signup OTP'}</button>
              ) : (
                <button type="button" className="btn primary" onClick={login} disabled={authLoading}>{authLoading ? 'Authenticating...' : 'Login'}</button>
              )}
            </div>
          </>
        ) : (
          <>
            <p className="muted">Enter OTP sent to your registered email. OTP valid for 5 minutes.</p>
            <div className="profile-create-grid">
              <label><span>OTP Code</span><input value={otpCode} onChange={(e) => setOtpCode(e.target.value)} placeholder="6-digit OTP" /></label>
            </div>
            <div className="actions">
              <button type="button" className="btn primary" onClick={verifyOtp} disabled={authLoading}>{authLoading ? 'Verifying...' : 'Verify OTP'}</button>
              <button type="button" className="btn" onClick={resendOtp} disabled={authLoading}>Resend OTP</button>
              <button type="button" className="btn" onClick={() => setAuthStage('credentials')} disabled={authLoading}>Back</button>
            </div>
          </>
        )}
      </section>
    </main>
  )
}
