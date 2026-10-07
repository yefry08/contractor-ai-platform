// Below this many contracts a rate swings on one or two contracts. Lives outside
// the "use client" heatmap so server components can read it: imported from a
// client module, a server component gets a client reference, not the number.
export const MIN_RELIABLE_CONTRACTS = 20;
