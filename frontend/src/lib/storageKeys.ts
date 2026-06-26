/**
 * Centralized localStorage key constants.
 * Always import from here — never hardcode these strings directly.
 */
export const STORAGE_KEYS = {
  ONBOARDING_DONE: 'wealth_monitor_onboarding_done',
  FAMILY_CONFIG: 'wealth_monitor_family_config',
  ONBOARDING_DRAFT: 'wealth_monitor_onboarding_draft',
  /** Prefix for the per-user portfolio cache. Actual key is `${PORTFOLIO_CACHE}_${uid}`. */
  PORTFOLIO_CACHE: 'wealth_monitor_portfolio_cache',
} as const;
