"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
type Order = { id: string; status: string; total_amount: string | number; created_at: string };
const money = (value: string | number) => `$${Number(value).toFixed(2)}`;
export default function CustomerOrdersPage() {
  const [orders, setOrders] = useState<Order[]>([]); const [notice, setNotice] = useState("");
  const load = useCallback(() => apiRequest<Order[]>("/api/orders").then(setOrders).catch((e: Error)=>setNotice(e.message)), []);
  useEffect(()=>{ void load(); const id=new URLSearchParams(window.location.search).get("placed"); if(id)setNotice(`Order ${id} was placed successfully.`); },[load]);
  async function cancel(id:string) { try { await apiRequest(`/api/orders/${id}/cancel`,{method:"POST"}); setNotice("Order cancelled and stock restored."); await load(); } catch(e) {setNotice(e instanceof Error?e.message:"Could not cancel this order.");} }
  return <ProtectedPage role="customer"><Header/><main className="shop-page"><div className="shop-page-heading"><span className="eyebrow">Your purchases</span><h1>Order history</h1><p>Track recent orders and revisit your skincare choices.</p></div>{notice&&<p className="inline-notice" role="status">{notice}</p>}<section className="order-list">{orders.map(order=><article className="order-row" key={order.id}><div><small>Order #{order.id.slice(0,8)}</small><h2>{new Date(order.created_at).toLocaleDateString()}</h2></div><span className={`status-pill status-${order.status.toLowerCase()}`}>{order.status}</span><b>{money(order.total_amount)}</b><Link className="text-link" href={`/customer/orders/${order.id}`}>View details</Link>{["pending","confirmed"].includes(order.status.toLowerCase())&&<button className="text-button" type="button" onClick={()=>void cancel(order.id)}>Cancel</button>}</article>)}{orders.length===0&&<div className="shop-empty"><h2>No orders yet</h2><p>Your completed checkouts will appear here.</p><Link className="button primary" href="/products">Browse products</Link></div>}</section></main></ProtectedPage>;
}
