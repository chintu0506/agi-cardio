export default function CreateProfilePage({
  profileForm,
  setProfileForm,
  creatingProfile,
  createCompleteProfile,
  setPatientView,
}) {
  return (
    <section className="panel create-profile-page">
      <p className="topbar-kicker">Patient Onboarding</p>
      <h2>Create New Profile</h2>
      <p className="muted">This page is dedicated only to profile creation. After saving, your new name appears in profile options automatically.</p>
      <div className="profile-create-grid">
        <label><span>Full Name</span><input autoFocus value={profileForm.full_name} onChange={(e) => setProfileForm((p) => ({ ...p, full_name: e.target.value }))} /></label>
        <label><span>Age</span><input type="number" value={profileForm.age} onChange={(e) => setProfileForm((p) => ({ ...p, age: e.target.value }))} /></label>
        <label><span>Sex</span><select value={profileForm.sex} onChange={(e) => setProfileForm((p) => ({ ...p, sex: e.target.value }))}><option value="">Select</option><option value="0">Female</option><option value="1">Male</option></select></label>
        <label><span>DOB</span><input type="date" value={profileForm.dob} onChange={(e) => setProfileForm((p) => ({ ...p, dob: e.target.value }))} /></label>
        <label><span>Phone</span><input value={profileForm.phone} onChange={(e) => setProfileForm((p) => ({ ...p, phone: e.target.value }))} /></label>
        <label><span>Email</span><input value={profileForm.email} onChange={(e) => setProfileForm((p) => ({ ...p, email: e.target.value }))} /></label>
        <label><span>Blood Group</span><input value={profileForm.blood_group} onChange={(e) => setProfileForm((p) => ({ ...p, blood_group: e.target.value }))} /></label>
        <label><span>Emergency Contact</span><input value={profileForm.emergency_contact} onChange={(e) => setProfileForm((p) => ({ ...p, emergency_contact: e.target.value }))} /></label>
        <label><span>Address</span><input value={profileForm.address} onChange={(e) => setProfileForm((p) => ({ ...p, address: e.target.value }))} /></label>
        <label><span>Allergies</span><input value={profileForm.allergies} onChange={(e) => setProfileForm((p) => ({ ...p, allergies: e.target.value }))} /></label>
        <label><span>Conditions</span><input value={profileForm.existing_conditions} onChange={(e) => setProfileForm((p) => ({ ...p, existing_conditions: e.target.value }))} /></label>
        <label><span>Notes</span><input value={profileForm.notes} onChange={(e) => setProfileForm((p) => ({ ...p, notes: e.target.value }))} /></label>
      </div>
      <div className="actions create-profile-actions">
        <button className="btn primary" onClick={createCompleteProfile} disabled={creatingProfile}>
          {creatingProfile ? 'Creating...' : 'Create Complete Profile'}
        </button>
        <button className="btn" onClick={() => setPatientView('workspace')} disabled={creatingProfile}>
          Back To Workspace
        </button>
      </div>
    </section>
  )
}
