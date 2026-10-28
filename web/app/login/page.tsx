"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { requestMagicLink } from "@/lib/api";
import Masthead from "@/components/editorial/Masthead";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const GOOGLE_ERRORS: Record<string, string> = {
  google: "Google sign-in didn't complete — try again.",
  "not-allowed": "That Google account isn't on this project's access list.",
};

const schema = z.object({ email: z.string().email("Invalid email") });
type Fields = z.infer<typeof schema>;

export default function LoginPage() {
  // useSearchParams needs a Suspense boundary for Next's static prerender
  return (
    <Suspense fallback={null}>
      <LoginInner />
    </Suspense>
  );
}

function LoginInner() {
  const [sent, setSent] = useState(false);
  const [email, setEmail] = useState("");
  const [sendError, setSendError] = useState<string | null>(null);
  const googleError = GOOGLE_ERRORS[useSearchParams().get("error") ?? ""];
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: Fields) => {
    setSendError(null);
    try {
      const res = await requestMagicLink(data.email);
      // Dev mode: backend returns the magic link directly — auto-follow it.
      if (res.dev_link) {
        window.location.href = res.dev_link;
        return;
      }
      setEmail(data.email);
      setSent(true);
    } catch (e) {
      setSendError(e instanceof Error ? e.message : "Could not send the link — try again");
    }
  };

  return (
    <div className="gq-page">
      <div className="gq2-login">
        <Masthead />

        <div className="gq2-login-card">
          {sent ? (
            <>
              <div className="gq2-login-card__eyebrow">Check your inbox</div>
              <p style={{ fontSize: 14.5, lineHeight: 1.7, textAlign: "center", margin: 0 }}>
                We sent a sign-in link to <strong>{email}</strong>.
                <br />
                It expires in 15 minutes.
              </p>
            </>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)}>
              <div className="gq2-login-card__eyebrow">Producers sign in</div>
              {googleError && <p className="gq2-login-err">{googleError}</p>}

              <a
                href={`${API_BASE}/auth/google/login`}
                className="gq-btn"
                style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  gap: 10, width: "100%", textDecoration: "none",
                }}
              >
                <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden>
                  <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.2C12.4 13.4 17.7 9.5 24 9.5z"/>
                  <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 2.9-2.3 5.4-4.8 7.1l7.6 5.9c4.5-4.1 7-10.2 7-17.5z"/>
                  <path fill="#FBBC05" d="M10.5 28.6a14.5 14.5 0 0 1 0-9.2l-7.9-6.2a24 24 0 0 0 0 21.6l7.9-6.2z"/>
                  <path fill="#34A853" d="M24 48c6.3 0 11.6-2.1 15.5-5.7l-7.6-5.9c-2.1 1.4-4.8 2.3-7.9 2.3-6.3 0-11.6-3.9-13.5-9.4l-7.9 6.2C6.5 42.6 14.6 48 24 48z"/>
                </svg>
                Continue with Google
              </a>

              <div className="gq2-login-div">or get a sign-in link</div>

              <label className="gq-label">Email address</label>
              <input
                className="gq-input"
                type="email"
                placeholder="you@condenast.in"
                autoComplete="email"
                {...register("email")}
              />
              {errors.email && (
                <p className="gq2-login-err" style={{ textAlign: "left", marginTop: 8 }}>
                  {errors.email.message}
                </p>
              )}
              {sendError && (
                <p className="gq2-login-err" style={{ textAlign: "left", marginTop: 8 }}>
                  {sendError}
                </p>
              )}
              <button
                type="submit"
                className="gq-btn gq-btn--ghost"
                disabled={isSubmitting}
                style={{ width: "100%", marginTop: 14 }}
              >
                {isSubmitting ? "Sending…" : "Send sign-in link"}
              </button>
            </form>
          )}
        </div>

        <div className="gq-foot">Produced on Cue</div>
      </div>
    </div>
  );
}
