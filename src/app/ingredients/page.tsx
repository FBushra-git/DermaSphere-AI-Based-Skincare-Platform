"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/Header";
import { apiRequest } from "@/lib/api";

type Ingredient = { id: string; name: string; description: string | null; common_uses: string | null; benefits: string | null; cautions: string | null };
type IngredientDetail = Ingredient & { products: { id: string; name: string; brand: string; price: string | number; image_url: string | null; available_quantity: number }[] };

export default function IngredientsPage() {
  const [items, setItems] = useState<Ingredient[]>([]);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<IngredientDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  useEffect(() => { apiRequest<Ingredient[]>("/api/ingredients").then(setItems).catch((reason: Error) => setError(reason.message)); }, []);
  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError("");
    try { setItems(await apiRequest<Ingredient[]>(`/api/ingredients?q=${encodeURIComponent(query.trim())}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not search ingredients."); }
    finally { setLoading(false); }
  }
  async function openIngredient(ingredient: Ingredient) {
    setSelected(null); setError("");
    try { setSelected(await apiRequest<IngredientDetail>(`/api/ingredients/${ingredient.id}`)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load this ingredient."); }
  }
  return <><Header/><main className="learning-page"><div className="learning-hero"><span className="eyebrow">INGREDIENT CLARITY</span><h1>Know what goes on your skin.</h1><p>Browse the ingredients listed in DermaSphere products and learn about their common uses, benefits, and cautions.</p><form className="learning-search" role="search" onSubmit={search}><label className="sr-only" htmlFor="ingredient-search">Search ingredients</label><input id="ingredient-search" value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Search an ingredient…"/><button className="button primary" type="submit" disabled={loading}>{loading?"Searching…":"Search"}</button></form></div>{error&&<p className="form-error" role="alert">{error}</p>}<section className="ingredient-grid" aria-label="Ingredients">{items.map((item,index)=><button className="ingredient-card" key={item.id} type="button" onClick={()=>void openIngredient(item)}><span className={`ingredient-art ingredient-art-${index%5}`} aria-hidden="true">✿</span><span className="eyebrow">INGREDIENT GUIDE</span><b>{item.name}</b><p>{item.description||item.common_uses||"Explore products containing this ingredient."}</p><span className="text-link">Learn more →</span></button>)}</section>{!items.length&&!error&&<div className="shop-empty"><h2>No ingredient entries yet</h2><p>Ingredient guides will appear as the catalog is set up.</p><Link className="button outline" href="/products">Explore products</Link></div>}{selected&&<div className="modal-backdrop" role="presentation" onClick={()=>setSelected(null)}><section className="ingredient-modal" role="dialog" aria-modal="true" aria-labelledby="ingredient-title" onClick={(event)=>event.stopPropagation()}><button className="modal-close" type="button" onClick={()=>setSelected(null)} aria-label="Close ingredient details">×</button><span className="eyebrow">INGREDIENT GUIDE</span><h2 id="ingredient-title">{selected.name}</h2>{selected.description&&<p>{selected.description}</p>}{selected.common_uses&&<div><h3>Common uses</h3><p>{selected.common_uses}</p></div>}{selected.benefits&&<div><h3>Potential benefits</h3><p>{selected.benefits}</p></div>}{selected.cautions&&<div className="ingredient-caution"><h3>Cautions</h3><p>{selected.cautions}</p></div>}<h3>Products containing {selected.name}</h3>{selected.products.length?<ul className="ingredient-product-list">{selected.products.map((product)=><li key={product.id}><Link href={`/products/${product.id}`}>{product.brand} — {product.name}</Link><span>{product.available_quantity>0?`$${Number(product.price).toFixed(2)}`:"Out of stock"}</span></li>)}</ul>:<p>No approved products currently list this ingredient.</p>}<p className="ingredient-note">Ingredient information is general and is not a substitute for personal medical advice. Review product labels and patch test new products.</p></section></div>}</main></>;
}
