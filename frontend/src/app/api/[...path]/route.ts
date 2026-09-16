import { NextResponse, type NextRequest } from "next/server";

/**
 * Server-side proxy to the Kayan API.
 *
 * The console calls its own `/api/...` so that the session cookie is first-party
 * (no cross-site cookies, no CORS) and the backend URL is never exposed to the browser.
 */
const BACKEND = (process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");

// The agent's LLM replies can take a while.
export const maxDuration = 120;

const HOP_BY_HOP = new Set([
  "connection", "keep-alive", "transfer-encoding", "upgrade", "proxy-authenticate",
  "proxy-authorization", "te", "trailer", "host", "content-length", "content-encoding",
]);

async function handler(request: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const target = `${BACKEND}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;

  const headers = new Headers();
  request.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "GET" || request.method === "HEAD" ? undefined : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ detail: "The API is unreachable" }, { status: 502 });
  }

  const out = new Headers();
  response.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) out.set(key, value);
  });
  // Preserve every Set-Cookie (sign-in, sign-out) rather than the folded single value.
  const cookies = response.headers.getSetCookie?.() ?? [];
  if (cookies.length) {
    out.delete("set-cookie");
    for (const cookie of cookies) out.append("set-cookie", cookie);
  }
  return new NextResponse(response.body, { status: response.status, headers: out });
}

export const GET = handler;
export const POST = handler;
export const PATCH = handler;
export const PUT = handler;
export const DELETE = handler;
