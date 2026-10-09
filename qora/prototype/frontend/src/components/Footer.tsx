import { Link } from "react-router-dom";
import { Sparkles, Github, Twitter, Linkedin } from "lucide-react";

export default function Footer() {
  return (
    <footer className="mt-24 border-t border-white/5 bg-black/20">
      <div className="mx-auto max-w-7xl px-4 py-12 sm:px-6">
        <div className="grid gap-10 md:grid-cols-4">
          <div>
            <Link to="/" className="mb-4 flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 font-display text-lg font-bold text-white">
                Q
              </span>
              <span className="font-display text-xl font-bold text-white">QORA</span>
            </Link>
            <p className="max-w-xs text-sm leading-relaxed text-slate-500">
              The consumer network for AI services. Discover vetted AI providers, order with confidence,
              and pay only when you're satisfied.
            </p>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Platform</h4>
            <ul className="space-y-2.5 text-sm text-slate-500">
              <li><Link to="/services" className="hover:text-slate-300">Explore services</Link></li>
              <li><Link to="/assistant" className="hover:text-slate-300">AI Concierge</Link></li>
              <li><Link to="/register" className="hover:text-slate-300">Become a provider</Link></li>
              <li><Link to="/wallet" className="hover:text-slate-300">Wallet</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Categories</h4>
            <ul className="space-y-2.5 text-sm text-slate-500">
              <li><Link to="/services?category=chatbots" className="hover:text-slate-300">Chatbots &amp; Assistants</Link></li>
              <li><Link to="/services?category=image-vision" className="hover:text-slate-300">Image &amp; Vision</Link></li>
              <li><Link to="/services?category=data-analytics" className="hover:text-slate-300">Data &amp; Analytics</Link></li>
              <li><Link to="/services?category=automation-agents" className="hover:text-slate-300">Automation &amp; Agents</Link></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-400">Company</h4>
            <p className="mb-4 text-sm text-slate-500">
              QORA is a demo platform showcasing an advanced full-stack architecture:
              FastAPI · React · PostgreSQL-ready.
            </p>
            <div className="flex gap-3 text-slate-500">
              <span className="rounded-lg border border-white/10 p-2 hover:text-slate-300"><Github size={16} /></span>
              <span className="rounded-lg border border-white/10 p-2 hover:text-slate-300"><Twitter size={16} /></span>
              <span className="rounded-lg border border-white/10 p-2 hover:text-slate-300"><Linkedin size={16} /></span>
            </div>
          </div>
        </div>
        <div className="mt-10 flex flex-wrap items-center justify-between gap-4 border-t border-white/5 pt-6 text-xs text-slate-600">
          <p>© {new Date().getFullYear()} QORA — Consumer AI Service Network. All rights reserved.</p>
          <p className="flex items-center gap-1.5">
            <Sparkles size={12} className="text-indigo-400" /> Built as an advanced full-stack demo
          </p>
        </div>
      </div>
    </footer>
  );
}
