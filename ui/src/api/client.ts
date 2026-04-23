const BASE = "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal });
  const body = await parseJson(res);
  if (!res.ok) {
    throw new ApiError(
      (body as { detail?: string } | null)?.detail ?? res.statusText,
      res.status,
      body,
    );
  }
  return body as T;
}

export async function apiPost<T>(
  path: string,
  data: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(data),
    signal,
  });
  const body = await parseJson(res);
  if (!res.ok) {
    throw new ApiError(
      (body as { detail?: string } | null)?.detail ?? res.statusText,
      res.status,
      body,
    );
  }
  return body as T;
}
