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
  forgotPasswordLogin,
  verifyOtp,
  resendOtp,
  setAuthStage,
}) {
  const title = authMode === 'signup' ? 'Sign Up' : authMode === 'forgot' ? 'Forgot Password' : 'Login'
  const subtitle = authMode === 'forgot'
    ? 'Use OTP on your mobile and set a new password.'
    : 'Signup uses OTP verification. Login uses password authentication.'
  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="topbar-main">
          <p className="topbar-kicker">AI Cardiovascular Suite</p>
          <h1>AGI CardioSense</h1>
          <p>Secure doctor and patient portal with OTP-enabled onboarding.</p>
        </div>
        <div className="status-grid">
          <div className="status-card"><span>System</span><strong>{health?.status === 'ok' ? 'Online' : 'Checking...'}</strong></div>
          <div className="status-card"><span>Model Accuracy</span><strong>{health ? `${health.accuracy}%` : '--'}</strong></div>
        </div>
      </header>

      {error && <div className="alert">{error}</div>}

      <section className="auth-grid">
        <aside className="panel auth-side">
          <h2>Clinical Access</h2>
          <p className="muted">Fast and secure entry for coordinated diagnosis and monitoring workflows.</p>
          <ul className="list">
            <li>One portal for doctor and patient journeys.</li>
            <li>OTP-verified registration with mobile support.</li>
            <li>Model predictions paired with actionable summaries.</li>
          </ul>
        </aside>

        <section className="panel auth-form-panel">
          <h2>{title}</h2>
          <p className="muted">{subtitle}</p>
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
                  <label><span>Mobile</span><input value={authForm.mobile} onChange={(e) => setAuthForm((p) => ({ ...p, mobile: e.target.value }))} placeholder="10-digit mobile" /></label>
                  <label><span>Password</span><input type="password" autoComplete="new-password" value={authForm.password} onChange={(e) => setAuthForm((p) => ({ ...p, password: e.target.value }))} /></label>
                  <label><span>Role</span>
                    <select value={authForm.role} onChange={(e) => setAuthForm((p) => ({ ...p, role: e.target.value }))}>
                      <option value="patient">Patient</option>
                      <option value="doctor">Doctor</option>
                    </select>
                  </label>
                </div>
              ) : authMode === 'forgot' ? (
                <div className="profile-create-grid">
                  <label><span>Registered Mobile</span><input value={authForm.mobile} onChange={(e) => setAuthForm((p) => ({ ...p, mobile: e.target.value }))} placeholder="10-digit mobile" /></label>
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
                ) : authMode === 'forgot' ? (
                  <button type="button" className="btn primary" onClick={forgotPasswordLogin} disabled={authLoading}>{authLoading ? 'Sending OTP...' : 'Send OTP To Login'}</button>
                ) : (
                  <>
                    <button type="button" className="btn primary" onClick={login} disabled={authLoading}>{authLoading ? 'Authenticating...' : 'Login'}</button>
                    <button type="button" className="btn" onClick={() => switchAuthMode('forgot')} disabled={authLoading}>Forgot Password (OTP)</button>
                  </>
                )}
              </div>
            </>
          ) : (
            <>
              <p className="muted">
                {authMode === 'forgot'
                  ? 'Enter OTP sent to your mobile and choose your new password.'
                  : 'Enter OTP sent to your registered email/mobile. OTP valid for 5 minutes.'}
              </p>
              <div className="profile-create-grid">
                <label><span>OTP Code</span><input value={otpCode} onChange={(e) => setOtpCode(e.target.value)} placeholder="6-digit OTP" /></label>
                {authMode === 'forgot' && (
                  <label>
                    <span>New Password</span>
                    <input
                      type="password"
                      autoComplete="new-password"
                      value={authForm.reset_password}
                      onChange={(e) => setAuthForm((p) => ({ ...p, reset_password: e.target.value }))}
                      placeholder="Minimum 6 characters"
                    />
                  </label>
                )}
              </div>
              <div className="actions">
                <button type="button" className="btn primary" onClick={verifyOtp} disabled={authLoading}>{authLoading ? 'Verifying...' : authMode === 'forgot' ? 'Verify OTP And Update Password' : 'Verify OTP'}</button>
                <button type="button" className="btn" onClick={resendOtp} disabled={authLoading}>Resend OTP</button>
                <button type="button" className="btn" onClick={() => setAuthStage('credentials')} disabled={authLoading}>Back</button>
              </div>
            </>
          )}
        </section>
      </section>
    </main>
  )
}
