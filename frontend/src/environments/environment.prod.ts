/**
 * Production environment — swapped in at build time by the `production`
 * configuration in angular.json (fileReplacements).
 *
 * A production bundle has no dev-server proxy, so every /api request must
 * carry this origin. Set `apiUrl` to the deployed backend origin before
 * building (see README → Deploying); it is baked into the bundle at build
 * time, not read at runtime.
 */
export const environment = {
  production: true,
  /**
   * Deployed API origin, no trailing slash.
   * REPLACE with the real backend URL for your deployment.
   */
  apiUrl: 'https://policygpt-api.example.gov',
};
