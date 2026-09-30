"use client";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { ProtectedPage } from "@/components/ProtectedPage";
import { apiRequest, notifyCartUpdated } from "@/lib/api";
type CartLine = { id: string; product_id: string; name: string; brand: string; image_url: string | null; unit_price: string | number; quantity: number; available_quantity: number; line_total: string | number };
type CartData = { items: CartLine[]; subtotal: string | number };
const money = (value: string | number) => `$${Number(value).toFixed(2)}`;
export default function CartPage() {
  const [cart, setCart] = useState<CartData>({ items: [], subtotal: 0 });
  const [address, setAddress] = useState(""); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState("");
  const hasUnavailableItems = cart.items.some((line) => line.quantity > line.available_quantity);
  const load = useCallback(() => apiRequest<CartData>("/api/cart").then(setCart).catch((e: Error) => setNotice(e.message)), []);
  useEffect(() => { void load(); }, [load]);
  async function update(line: CartLine, quantity: number) {
    try { if (quantity < 1) await apiRequest(`/api/cart/items/${line.id}`, { method: "DELETE" }); else await apiRequest(`/api/cart/items/${line.id}`, { method: "PATCH", body: JSON.stringify({ quantity }) }); notifyCartUpdated(); await load(); }
    catch (e) { setNotice(e instanceof Error ? e.message : "Could not update your cart."); }
  }
  async function checkout(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setNotice("");
    try { const order = await apiRequest<{ id: string }>("/api/orders", { method: "POST", body: JSON.stringify({ shipping_address: address }) }); notifyCartUpdated(); window.location.assign(`/customer/orders?placed=${encodeURIComponent(order.id)}`); }
    catch (e) { setNotice(e instanceof Error ? e.message : "Checkout could not be completed."); setBusy(false); }
  }
  return <ProtectedPage role="customer"><Header/><main className="shop-page"><div className="shop-page-heading"><span className="eyebrow">Almost yours</span><h1>Your shopping bag</h1><p>Review your items and delivery details.</p></div>{notice&&<p className="form-error" role="alert">{notice}</p>}{cart.items.length===0?<section className="shop-empty"><span aria-hidden="true">♧</span><h2>Your bag is empty</h2><p>Find products that fit your skin and routine.</p><Link className="button primary" href="/products">Shop skincare</Link></section>:<div className="cart-layout"><section className="cart-lines" aria-label="Cart items">{cart.items.map(line=><article className="cart-line" key={line.id}><Link className="cart-line-image" href={`/products/${line.product_id}`}>{line.image_url?<img src={line.image_url} alt=""/>:<span aria-hidden="true">✿</span>}</Link><div className="cart-line-info"><small>{line.brand}</small><h2><Link href={`/products/${line.product_id}`}>{line.name}</Link></h2><b>{money(line.unit_price)}</b><span className="stock">{line.available_quantity} available</span><div className="quantity-control"><button type="button" onClick={()=>void update(line,line.quantity-1)} aria-label={`Remove one ${line.name}`}>−</button><span>{line.quantity}</span><button type="button" onClick={()=>void update(line,line.quantity+1)} disabled={line.quantity>=line.available_quantity} aria-label={`Add one ${line.name}`}>+</button></div></div><b className="cart-line-total">{money(line.line_total)}</b><button className="text-button remove-line" type="button" onClick={()=>void update(line,0)}>Remove</button></article>)}</section><form className="checkout-card" onSubmit={checkout}><h2>Order summary</h2><label htmlFor="shipping-address">Delivery address</label><textarea id="shipping-address" value={address} onChange={e=>setAddress(e.target.value)} required minLength={8} maxLength={500} placeholder="Street, city, postal code"/>{hasUnavailableItems&&<p className="form-error" role="alert">One or more items exceed current stock. Reduce the quantity or remove the unavailable item to continue.</p>}<div className="checkout-total"><span>Subtotal</span><b>{money(cart.subtotal)}</b></div><p className="checkout-note">Shipping and any applicable taxes will be confirmed with your order.</p><button className="button primary" type="submit" disabled={busy||hasUnavailableItems}>{busy?"Placing order…":"Place order"}</button></form></div>}</main></ProtectedPage>;
}
