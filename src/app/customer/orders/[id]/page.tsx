"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Header } from "@/components/Header";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest } from "@/lib/api";
type OrderDetail={id:string;status:string;total_amount:string|number;shipping_address:string;created_at:string;items:{product_id:string;product_name:string;quantity:number;unit_price:string|number}[]};
const money=(value:string|number)=>`$${Number(value).toFixed(2)}`;
export default function OrderDetailPage(){
 const {id}=useParams<{id:string}>();const [order,setOrder]=useState<OrderDetail|null>(null);const [error,setError]=useState("");
 useEffect(()=>{apiRequest<OrderDetail>(`/api/orders/${id}`).then(setOrder).catch((e:Error)=>setError(e.message));},[id]);
 return <ProtectedPage role="customer"><Header/><main className="shop-page"><div className="shop-page-heading"><span className="eyebrow">Order details</span><h1>{order?`Order #${order.id.slice(0,8)}`:"Your order"}</h1><Link className="text-link" href="/customer/orders">← Back to order history</Link></div>{error&&<p className="form-error" role="alert">{error}</p>}{order&&<section className="order-detail-card"><div className="order-detail-head"><span className={`status-pill status-${order.status.toLowerCase()}`}>{order.status}</span><span>Placed {new Date(order.created_at).toLocaleDateString()}</span></div><h2>Items</h2>{order.items.map((item,index)=><div className="order-detail-item" key={`${item.product_id}-${index}`}><Link href={`/products/${item.product_id}`}>{item.product_name}</Link><span>Qty {item.quantity}</span><b>{money(Number(item.unit_price)*item.quantity)}</b></div>)}<div className="checkout-total"><span>Total</span><b>{money(order.total_amount)}</b></div><h2>Delivery address</h2><p>{order.shipping_address}</p></section>}</main></ProtectedPage>;
}
