type RuntimeEnv = {
  VITE_SUPABASE_URL?: string;
  VITE_SUPABASE_ANON_KEY?: string;
  VITE_SUPABASE_REDIRECT_URL?: string;
};

declare global {
  interface Window {
    __OGI_RUNTIME_CONFIG__?: RuntimeEnv;
  }
}

const runtimeEnv: RuntimeEnv =
  typeof window !== "undefined" && window.__OGI_RUNTIME_CONFIG__
    ? window.__OGI_RUNTIME_CONFIG__
    : {};

export function getEnv(key: keyof RuntimeEnv): string | undefined {
  const runtimeValue = runtimeEnv[key];
  if (runtimeValue && runtimeValue.length > 0) return runtimeValue;

  const buildValue = import.meta.env[key];
  if (typeof buildValue === "string" && buildValue.length > 0) return buildValue;

  return undefined;
}
