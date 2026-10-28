import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Anyone without a session lands on /login. Share links stay public —
// they're the view-only surface for people who should never see the rest.
// Presence of the cookie is a routing hint only; the API still verifies
// the signed session on every request.
const PUBLIC_PATHS = [/^\/$/, /^\/welcome/, /^\/login/, /^\/share\//, /^\/auth\//, /^\/privacy/, /^\/terms/];

export function middleware(req: NextRequest) {
  // Local dev has no cookie at all — the backend auto-signs-in every request.
  if (process.env.NODE_ENV === "development") {
    return NextResponse.next();
  }
  const { pathname } = req.nextUrl;
  if (PUBLIC_PATHS.some((p) => p.test(pathname))) {
    // Signed-out visitors to the root get the server-rendered public page,
    // so crawlers (Google's OAuth verification included) see real content.
    if (pathname === "/" && !req.cookies.get("cue_session")) {
      return NextResponse.rewrite(new URL("/welcome", req.url));
    }
    return NextResponse.next();
  }
  if (!req.cookies.has("cue_session")) {
    const login = req.nextUrl.clone();
    login.pathname = "/login";
    return NextResponse.redirect(login);
  }
  return NextResponse.next();
}

export const config = {
  matcher: [
    // Everything except Next internals, the API proxy, and any static file
    // (anything with a dot — logos, fonts, email assets)
    "/((?!_next/static|_next/image|favicon.ico|api/|.*\\..*).*)",
  ],
};
