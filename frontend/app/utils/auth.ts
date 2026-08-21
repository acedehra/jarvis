/**
 * J.A.R.V.I.S. Frontend Authentication & Session Utilities
 * Manages API key persistence in browser sessionStorage and handles authenticated requests.
 */

export const SESSION_STORAGE_KEY = "jarvis_api_key";
export const UNAUTHORIZED_EVENT = "jarvis:unauthorized";

/**
 * Retrieves the stored API key from browser sessionStorage.
 */
export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    return sessionStorage.getItem(SESSION_STORAGE_KEY);
  } catch (e) {
    console.error("Failed to access sessionStorage:", e);
    return null;
  }
}

/**
 * Saves the API key to browser sessionStorage.
 */
export function setStoredApiKey(key: string): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(SESSION_STORAGE_KEY, key.trim());
  } catch (e) {
    console.error("Failed to set key in sessionStorage:", e);
  }
}

/**
 * Clears the API key from browser sessionStorage and emits an unauthorized event.
 */
export function clearStoredApiKey(): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(SESSION_STORAGE_KEY);
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  } catch (e) {
    console.error("Failed to clear key from sessionStorage:", e);
  }
}

/**
 * Resolves the backend base URL.
 */
export function getApiBaseUrl(): string {
  if (process.env.NEXT_PUBLIC_API_URL) {
    return process.env.NEXT_PUBLIC_API_URL;
  }
  if (typeof window !== "undefined") {
    return `http://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

/**
 * Generates authentication headers including the active session API key.
 */
export function getAuthHeaders(customHeaders?: HeadersInit): HeadersInit {
  const apiKey = getStoredApiKey();
  const headers: Record<string, string> = {};

  if (apiKey) {
    headers["X-API-Key"] = apiKey;
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  if (customHeaders) {
    if (customHeaders instanceof Headers) {
      customHeaders.forEach((value, key) => {
        headers[key] = value;
      });
    } else if (Array.isArray(customHeaders)) {
      customHeaders.forEach(([key, value]) => {
        headers[key] = value;
      });
    } else {
      Object.assign(headers, customHeaders);
    }
  }

  return headers;
}

/**
 * Performs an authenticated HTTP fetch call.
 * Automatically attaches API key headers and triggers unauthorized handler on 401.
 */
export async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const headers = getAuthHeaders(init?.headers);
  const response = await fetch(url, {
    ...init,
    headers,
  });

  if (response.status === 401) {
    // If backend rejects credentials, invalidate stored key
    clearStoredApiKey();
  }

  return response;
}

/**
 * Validates an API key against the backend /api/auth/verify endpoint.
 */
export async function validateApiKey(
  key: string,
  apiBaseUrl?: string
): Promise<{ success: boolean; message?: string }> {
  const baseUrl = apiBaseUrl || getApiBaseUrl();
  const trimmed = key.trim();
  
  if (!trimmed) {
    return { success: false, message: "Please enter an API key." };
  }

  try {
    const res = await fetch(`${baseUrl}/api/auth/verify`, {
      method: "GET",
      headers: {
        "X-API-Key": trimmed,
      },
    });

    if (res.ok) {
      return { success: true };
    }

    if (res.status === 401) {
      return { success: false, message: "Invalid API key. Please check your credentials and try again." };
    }

    return { success: false, message: `Server returned error (${res.status}). Ensure the backend is running.` };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : "Network error";
    return {
      success: false,
      message: `Failed to connect to Jarvis backend at ${baseUrl} (${errorMsg}).`,
    };
  }
}

/**
 * Constructs the authenticated WebSocket connection URL.
 */
export function getAuthenticatedWsUrl(threadId: string, apiBaseUrl?: string): string {
  const apiBase = apiBaseUrl || getApiBaseUrl();
  const wsBase = apiBase.replace(/^http/, "ws");
  const apiKey = getStoredApiKey() || "";
  return `${wsBase}/api/chat?session_id=${threadId}&api_key=${encodeURIComponent(apiKey)}`;
}
