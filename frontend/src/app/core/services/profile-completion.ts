import { CitizenProfileResponse } from '../models/auth.models';

/**
 * Fields a profile needs before it can drive eligibility checking.
 *
 * Single source of truth: the profile page marks a profile complete with the
 * same rule, so the dashboard card and the page can never disagree.
 */
export function isCitizenProfileComplete(
  profile: Partial<CitizenProfileResponse> | null | undefined
): boolean {
  if (!profile) {
    return false;
  }

  return !!(
    profile.gender &&
    profile.date_of_birth &&
    profile.occupation &&
    profile.state
  );
}
