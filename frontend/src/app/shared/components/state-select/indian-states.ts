/**
 * The 28 states and 8 Union Territories of India, alphabetically ordered.
 *
 * Single source of truth for every form field where a user must choose a
 * state, so the string stored on the backend (plain `state` columns) stays
 * consistent across citizen profiles, role requests, finder, policy and
 * scheme forms.
 */
export const INDIAN_STATES: string[] = [
  'Andhra Pradesh',
  'Arunachal Pradesh',
  'Assam',
  'Bihar',
  'Chhattisgarh',
  'Goa',
  'Gujarat',
  'Haryana',
  'Himachal Pradesh',
  'Jharkhand',
  'Karnataka',
  'Kerala',
  'Madhya Pradesh',
  'Maharashtra',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Odisha',
  'Punjab',
  'Rajasthan',
  'Sikkim',
  'Tamil Nadu',
  'Telangana',
  'Tripura',
  'Uttar Pradesh',
  'Uttarakhand',
  'West Bengal',
];

export const INDIAN_UNION_TERRITORIES: string[] = [
  'Andaman and Nicobar Islands',
  'Chandigarh',
  'Dadra and Nagar Haveli and Daman and Diu',
  'Delhi',
  'Jammu and Kashmir',
  'Ladakh',
  'Lakshadweep',
  'Puducherry',
];

/** All 36 states and Union Territories, as shown in the state dropdown. */
export const INDIAN_STATES_AND_UTS: string[] = [
  ...INDIAN_STATES,
  ...INDIAN_UNION_TERRITORIES,
];
