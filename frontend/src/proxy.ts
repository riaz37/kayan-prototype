import { NextResponse, type NextRequest } from "next/server";
import { LOCALE_COOKIE, defaultLocale, isLocale } from "@/lib/i18n/config";

const SESSION_COOKIE = "kayan_session";

const ONE_YEAR = 60 * 60 * 24 * 365;

/**
 * Every console URL carries its locale (`/ar/...`, `/en/...`) so the server
 * renders the right `lang`/`dir` on first paint. Bare paths are redirected to
 * the visitor's last-used locale (cookie), defaulting to Arabic.
 */
export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const first = pathname.split("/")[1];

  if (isLocale(first)) {
    // Send signed-out visitors to the sign-in page before rendering the console.
    const rest = pathname.slice(first.length + 1) || "/";
    const signedIn = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
    if (!signedIn && rest !== "/login" && !rest.startsWith("/login/")) {
      const url = request.nextUrl.clone();
      url.pathname = `/${first}/login`;
      url.search = "";
      url.searchParams.set("next", pathname + request.nextUrl.search);
      return NextResponse.redirect(url);
    }
    // Remember the locale the visitor is actually using (covers shared links too).
    if (request.cookies.get(LOCALE_COOKIE)?.value === first) return NextResponse.next();
    const res = NextResponse.next();
    res.cookies.set(LOCALE_COOKIE, first, { path: "/", maxAge: ONE_YEAR, sameSite: "lax" });
    return res;
  }

  const saved = request.cookies.get(LOCALE_COOKIE)?.value;
  const locale = isLocale(saved) ? saved : defaultLocale;
  const url = request.nextUrl.clone();
  url.pathname = `/${locale}${pathname === "/" ? "" : pathname}`;
  return NextResponse.redirect(url);
}

export const config = {
  // Skip Next internals and any file with an extension (fonts, icons, robots.txt…).
  matcher: ["/((?!_next/|api/|.*\\.[\\w]+$).*)"],
};
