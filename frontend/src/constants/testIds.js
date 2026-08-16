/* Test IDs — all interactive elements + critical info elements. */
export const LANDING = {
    heroTitle: 'landing-hero-title',
    ctaDemo: 'landing-cta-demo',
    ctaLogin: 'landing-cta-login',
    featureCard: (k) => `landing-feature-${k}`,
    demoBanner: 'landing-demo-banner',
};

export const LOGIN = {
    form: 'login-form',
    email: 'login-email-input',
    password: 'login-password-input',
    submit: 'login-submit-button',
    error: 'login-error-message',
    demoLink: 'login-demo-link',
};

export const SHELL = {
    root: 'app-shell-root',
    sidebar: 'app-shell-sidebar',
    header: 'app-shell-header',
    userMenu: 'app-shell-user-menu',
    logout: 'app-shell-logout',
    demoRibbon: 'app-shell-demo-ribbon',
    nav: (k) => `nav-link-${k}`,
};

export const COMMAND = {
    page: 'command-centre-page',
    freshness: 'command-centre-freshness',
    kpiRevenue: 'kpi-revenue-mtd',
    kpiOutletsAtRisk: 'kpi-outlets-at-risk',
    kpiOpportunity: 'kpi-estimated-opportunity',
    kpiVerified: 'kpi-verified-recovery',
    emptyState: 'command-centre-empty-state',
    filterBar: 'command-centre-filter-bar',
};

export const DEMO = {
    startButton: 'demo-start-button',
    ribbon: 'demo-ribbon',
};

// Legacy compat with template
export const HOME = { emergentLink: 'home-emergent-link' };
