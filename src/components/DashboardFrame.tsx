import Link from "next/link";
import { Header } from "@/components/Header";

type Item = { label: string; href: string; icon: string };
export function DashboardFrame({ title, eyebrow, nav, children }: { title: string; eyebrow: string; nav: Item[]; children: React.ReactNode }) {
  return <><Header/><main className="account-layout"><aside className="dashboard-sidebar"><Link className="sidebar-brand" href="/">✿ DermaSphere</Link><span className="sidebar-label">{eyebrow}</span><nav>{nav.map(item=><Link key={item.href} href={item.href}><span>{item.icon}</span>{item.label}</Link>)}</nav><Link className="sidebar-back" href="/">← Back to the shop</Link></aside><section className="dashboard-main"><div className="dashboard-heading"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1></div><span className="dashboard-avatar">✿</span></div>{children}</section></main></>;
}
export function StatCards({ items }: { items: { label: string; value: string | number; icon: string }[] }) {
  return <div className="stat-grid">{items.map(item=><article className="stat-card" key={item.label}><span>{item.icon}</span><div><small>{item.label}</small><b>{item.value}</b></div></article>)}</div>;
}
