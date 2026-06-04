export function usePageContext(): {
  customer_id: number | null;
  opportunity_id: number | null;
} {
  // TODO: wire to page store once one exists
  return { customer_id: null, opportunity_id: null };
}
