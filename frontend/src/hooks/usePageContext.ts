export function usePageContext(): {
  customer_id: number | null;
  opportunity_id: number | null;
} {
  if (process.env.NODE_ENV !== "production") {
    console.warn("usePageContext: stub returning nulls — wire to page store when available");
  }
  return { customer_id: null, opportunity_id: null };
}
