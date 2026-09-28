"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { ProtectedPage } from "@/components/ProtectedPage";
import { ProductGrid, type CatalogProduct } from "@/components/ProductGrid";
import { apiRequest } from "@/lib/api";
export default function WishlistPage() {
  const [items, setItems] = useState<CatalogProduct[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(() => apiRequest<CatalogProduct[]>("/api/wishlist").then(setItems).catch((e: Error) => setError(e.message)), []);
  useEffect(() => { void load(); }, [load]);
  return <ProtectedPage role="customer"><Header/><main className="shop-page"><div className="shop-page-heading"><span className="eyebrow">Saved for your routine</span><h1>Your wishlist</h1><p>Keep your trusted skincare picks together.</p></div>{error&&<p className="form-error" role="alert">{error}</p>}{items.length?<ProductGrid items={items}/>:<section className="shop-empty"><span aria-hidden="true">♡</span><h2>Your wishlist is waiting</h2><p>Save products you want to explore later.</p><Link className="button primary" href="/products">Explore products</Link></section>}</main></ProtectedPage>;
}
