"use client";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { requestMagicLink } from "@/lib/api";

const schema = z.object({ email: z.string().email("Invalid email") });
type Fields = z.infer<typeof schema>;

export default function LoginPage() {
  const [sent, setSent] = useState(false);
  const [email, setEmail] = useState("");
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Fields>({ resolver: zodResolver(schema) });

  const onSubmit = async (data: Fields) => {
    const res = await requestMagicLink(data.email);
    // Dev mode: backend returns the magic link directly — auto-follow it.
    if (res.dev_link) {
      window.location.href = res.dev_link;
      return;
    }
    setEmail(data.email);
    setSent(true);
  };

  return (
    <main className="page" style={{ paddingTop: "80px" }}>
      <div className="upload">
        <div className="meta meta--red">Sign in</div>
        <h1 className="display" style={{ marginTop: "12px", fontSize: "44px" }}>
          Cue<span className="red">.</span>
        </h1>
        <p className="voice" style={{ marginTop: "16px" }}>
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
