/**
 * Resolves the backend API origin for the axios client.
 * `NEXT_PUBLIC_*` values are inlined at Next.js build time.
 * Empty or whitespace-only values are treated as unset (so `NEXT_PUBLIC_API_URL=`
 * in a copied `.env.example` still falls through).
 */
function pickNonEmptyOrigin(value: string | undefined): string | undefined {
  const t = value?.trim();
  return t ? t : undefined;
}

export function getApiBaseUrl(): string {
  return (
    pickNonEmptyOrigin(process.env.NEXT_PUBLIC_API_URL) ??
    pickNonEmptyOrigin(process.env.NEXT_PUBLIC_BACKEND_URL) ??
    "http://localhost:8000"
  );
}
