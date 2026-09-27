const base = import.meta.env.VITE_API_URL ?? "/api";
export async function api<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    const data = await response
      .json()
      .catch(() => ({ detail: "Server unavailable" }));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request could not be processed (${response.status}).`,
    );
  }
  return response.json();
}
