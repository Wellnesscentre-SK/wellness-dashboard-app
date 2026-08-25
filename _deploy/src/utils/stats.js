export function emptyStats() {
  return {
    new: { WC: 0, TA: 0, YD: 0, MW: 0, total: 0 },
    followup: { WC: 0, TA: 0, YD: 0, MW: 0, total: 0 },
    gender: { m: 0, f: 0, o: 0, total: 0 },
    concerns: {},
    stakeholders: {},
    referral: {},
    modes: {},
    needsReview: false,
  }
}

export function computeStats(caseRows) {
  const s = emptyStats()
  if (!caseRows || !caseRows.length) return s

  for (const r of caseRows) {
    const group = s[r.case_type]
    if (group) {
      group[r.vertical] = r.total_cases
      group.total += r.total_cases
    }
    s.gender.m += r.gender_male
    s.gender.f += r.gender_female
    s.gender.o += r.gender_other
    s.gender.total += r.total_cases

    for (const [key, val] of Object.entries({
      concern_anxiety: r.concern_anxiety,
      concern_stress: r.concern_stress,
      concern_career: r.concern_career,
      concern_interpersonal: r.concern_interpersonal,
      concern_self_dev: r.concern_self_dev,
      concern_clinical: r.concern_clinical,
      concern_addiction: r.concern_addiction,
      concern_medical: r.concern_medical,
      concern_suicidal: r.concern_suicidal,
    })) {
      s.concerns[key] = (s.concerns[key] || 0) + val
    }
    for (const [key, val] of Object.entries({
      stake_ug: r.stake_ug,
      stake_pg: r.stake_pg,
      stake_phd: r.stake_phd,
      stake_dual: r.stake_dual,
      stake_faculty: r.stake_faculty,
      stake_employee_family: r.stake_employee_family,
      stake_postdoc: r.stake_postdoc,
      stake_unidentified: r.stake_unidentified,
    })) {
      s.stakeholders[key] = (s.stakeholders[key] || 0) + val
    }
    for (const [key, val] of Object.entries({
      referral_self: r.referral_self,
      referral_director: r.referral_director,
      referral_dean: r.referral_dean,
      referral_friend: r.referral_friend,
      referral_mitr: r.referral_mitr,
    })) {
      s.referral[key] = (s.referral[key] || 0) + val
    }
    for (const [key, val] of Object.entries({
      mode_online: r.mode_online,
      mode_in_person: r.mode_in_person,
      mode_phone: r.mode_phone,
    })) {
      s.modes[key] = (s.modes[key] || 0) + val
    }
    if (r.needs_review) s.needsReview = true
  }
  return s
}

export const CONCERN_LABELS = {
  concern_anxiety: 'Anxiety',
  concern_stress: 'Stress',
  concern_career: 'Career',
  concern_interpersonal: 'Interpersonal',
  concern_self_dev: 'Self Development',
  concern_clinical: 'Clinical',
  concern_addiction: 'Addiction',
  concern_medical: 'Medical',
  concern_suicidal: 'Suicidal',
}

export const STAKEHOLDER_LABELS = {
  stake_ug: 'UG',
  stake_pg: 'PG',
  stake_phd: 'PhD',
  stake_dual: 'Dual Degree',
  stake_faculty: 'Faculty',
  stake_employee_family: 'Employee/Family',
  stake_postdoc: 'Postdoc',
  stake_unidentified: 'Unidentified',
}

export const REFERRAL_LABELS = {
  referral_self: 'Self',
  referral_director: 'Director',
  referral_dean: 'Dean',
  referral_friend: 'Friend',
  referral_mitr: 'Mithr',
}

export const MODE_LABELS = {
  mode_online: 'Online',
  mode_in_person: 'In-person',
  mode_phone: 'Phone',
}

const COLORS = {
  WC: '#4472C4',
  TA: '#ED7D31',
  YD: '#A5A5A5',
  MW: '#FFC000',
  new: '#4472C4',
  followup: '#ED7D31',
}

export function verticalColor(v) {
  return COLORS[v] || '#94a3b8'
}
