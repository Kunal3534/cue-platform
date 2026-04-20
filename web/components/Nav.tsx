import Link from "next/link";
import WordmarkStrip from "./WordmarkStrip";

export default function Nav() {
  return (
    <nav className="border-b border-hair bg-chalk">
      <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
        <Link href="/" className="flex items-center gap-4">
          <WordmarkStrip width={140} tilt={-5} />
        </Link>
        <div className="flex items-center gap-6 font-mono text-xs uppercase tracking-wider text-slate/70">
          <Link href="/" className="hover:text-slate">Projects</Link>
          <Link href="/upload" className="hover:text-slate">New project</Link>
        </div>
      </div>
    </nav>
  );
}
