"use client";
import { Suspense, useState } from "react";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { requestMagicLink } from "@/lib/api";

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
      setSendError(
        e instanceof Error ? e.message : "Could not send the link — try again",
      );
    }
  };

  return (
    <main className="page" style={{ paddingTop: "80px" }}>
      <div className="upload">
        <Image
          src="/cue-mark.svg"
          alt="Cue"
          width={160}
          height={56}
          priority
          style={{ height: "56px", width: "auto", display: "block", marginBottom: "24px" }}
        />
        <div className="meta meta--red">Sign in</div>
        <p
          className="voice"
          style={{ marginTop: "12px", fontSize: "20px", lineHeight: 1.3 }}
        >
          Pre-production, the way the room works.
        </p>

        {sent ? (
          <div
            className="card"
            style={{ marginTop: "40px", padding: "32px 36px" }}
          >
            <div className="meta" style={{ marginBottom: "12px" }}>
              Check your inbox
            </div>
            <p className="voice" style={{ fontSize: "16px" }}>
              We sent a sign-in link to{" "}
              <span className="mono-sm">{email}</span>. Click it to continue —
              link expires in 15 minutes.
            </p>
          </div>
        ) : (
          <form
            onSubmit={handleSubmit(onSubmit)}
            style={{ marginTop: "40px" }}
          >
            {googleError && (
              <p className="mono-xs" style={{ color: "var(--cue-red)", marginBottom: "16px" }}>
                {googleError}
              </p>
            )}
            <a
              href={`${API_BASE}/auth/google/login`}
              className="btn btn--primary"
              style={{
                display: "flex", alignItems: "center", justifyContent: "center",
                gap: 10, marginBottom: 24, textDecoration: "none",
              }}
            >
              <svg width="17" height="17" viewBox="0 0 48 48" aria-hidden>
                <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.2C12.4 13.4 17.7 9.5 24 9.5z"/>
                <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 2.9-2.3 5.4-4.8 7.1l7.6 5.9c4.5-4.1 7-10.2 7-17.5z"/>
                <path fill="#FBBC05" d="M10.5 28.6a14.5 14.5 0 0 1 0-9.2l-7.9-6.2a24 24 0 0 0 0 21.6l7.9-6.2z"/>
                <path fill="#34A853" d="M24 48c6.3 0 11.6-2.1 15.5-5.7l-7.6-5.9c-2.1 1.4-4.8 2.3-7.9 2.3-6.3 0-11.6-3.9-13.5-9.4l-7.9 6.2C6.5 42.6 14.6 48 24 48z"/>
              </svg>
              Continue with Google
            </a>
            <div
              className="mono-xs"
              style={{ color: "#999", margin: "0 0 20px", display: "flex", alignItems: "center", gap: 12 }}
            >
              <span style={{ flex: 1, height: 1, background: "#E3E3E3" }} />
              or get a sign-in link
              <span style={{ flex: 1, height: 1, background: "#E3E3E3" }} />
            </div>
            <label
              className="lbl"
              style={{ display: "block", marginBottom: "10px" }}
            >
              Email address
            </label>
            <div className="chat-input" style={{ marginBottom: "16px" }}>
              <input
                type="email"
                placeholder="kunal@pixis.ai"
                autoComplete="email"
                {...register("email")}
              />
            </div>
            {errors.email && (
              <p className="mono-xs" style={{ color: "var(--cue-red)", marginBottom: "12px" }}>
                {errors.email.message}
              </p>
            )}
            {sendError && (
              <p className="mono-xs" style={{ color: "var(--cue-red)", marginBottom: "12px" }}>
                {sendError}
              </p>
            )}
            <button
              type="submit"
              className="btn btn--primary"
              disabled={isSubmitting}
            >
              {isSubmitting ? "Sending…" : "Send sign-in link →"}
            </button>
          </form>
        )}
      </div>
    </main>
  );
}
