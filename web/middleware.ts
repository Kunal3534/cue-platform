import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Dev mode: no auth on the frontend. The backend auto-signs-in every request
// as DEV_AUTO_LOGIN_EMAIL when that env var is set, so no cookie is needed.
// When we're ready to ship proper auth, restore the /login redirect below.
export function middleware(_req: NextRequest) {
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
