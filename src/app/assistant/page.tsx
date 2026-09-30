"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { ProtectedPage } from "@/components/ProtectedPage";
import { useAuth } from "@/components/AuthProvider";
import { apiRequest, notifyCartUpdated } from "@/lib/api";

type Option = { id: string; name: string };
type SuggestedProduct = { id: string; name: string; brand: string; price: string | number; image_url: string | null; available_quantity: number; reason: string };
const promptSuggestions = [
  "Build a simple morning routine for sensitive skin",
  "Suggest a moisturizer under $30 for dry skin",
  "What ingredients can support my skin barrier?",
];
type Conversation = { id: string; query: string; response: string; created_at: string; recommendations: { product_id: string; product_name: string; reason: string }[] };
type ChatResponse = { conversation_id: string; response: string; recommendations: SuggestedProduct[] };

function SuggestedProductCard({ product }: { product: SuggestedProduct }) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");

  async function addToBag() {
    setBusy(true);
    setNotice("");
    try {
      await apiRequest("/api/cart/items", {
        method: "POST",
        body: JSON.stringify({ product_id: product.id, quantity: 1 }),
      });
      notifyCartUpdated();
      setNotice("Added to bag.");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Could not add this product.");
    } finally {
      setBusy(false);
    }
  }

  return <article className="assistant-product"><Link href={`/products/${product.id}`}>{product.image_url?<img src={product.image_url} alt=""/>:<span className="assistant-product-placeholder">✿</span>}</Link><div><small>{product.brand}</small><h3><Link href={`/products/${product.id}`}>{product.name}</Link></h3><b>${Number(product.price).toFixed(2)}</b><p>{product.reason}</p><button className="button primary" type="button" onClick={()=>void addToBag()} disabled={busy||product.available_quantity<1}>{busy?"Adding…":"Add to bag"}</button>{notice&&<small role="status">{notice}</small>}</div></article>;
}

export default function AssistantPage() {
  const { user } = useAuth();
  const [skinTypes, setSkinTypes] = useState<Option[]>([]);
  const [concerns, setConcerns] = useState<Option[]>([]);
  const [categories, setCategories] = useState<Option[]>([]);
  const [history, setHistory] = useState<Conversation[]>([]);
  const [answer, setAnswer] = useState<ChatResponse | null>(null);
  const [restoredConversation, setRestoredConversation] = useState<Conversation | null>(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      apiRequest<Option[]>("/api/skin-types"),
      apiRequest<Option[]>("/api/skin-concerns"),
      apiRequest<Option[]>("/api/categories"),
      apiRequest<Conversation[]>("/api/ai/history"),
    ]).then(([types, skinConcerns, categoryRows, conversations]) => {
      setSkinTypes(types); setConcerns(skinConcerns); setCategories(categoryRows); setHistory(conversations);
    }).catch((reason: Error) => setError(reason.message));
  }, []);

  async function ask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setAnswer(null); setRestoredConversation(null);
    const form = new FormData(event.currentTarget);
    const budgetValue = String(form.get("budget") || "").trim();
    const payload = {
      query: query.trim(),
      skin_type_id: String(form.get("skin_type_id") || "") || null,
      skin_concern_ids: form.getAll("concerns").map(String),
      category_id: String(form.get("category_id") || "") || null,
      budget_max: budgetValue ? Number(budgetValue) : null,
    };
    try {
      const result = await apiRequest<ChatResponse>("/api/ai/chat", { method: "POST", body: JSON.stringify(payload) });
      setAnswer(result);
      setHistory(await apiRequest<Conversation[]>("/api/ai/history"));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "The assistant could not respond. Please try again.");
    } finally { setBusy(false); }
  }

  return <ProtectedPage role={user?.role === "seller" ? "seller" : "customer"}><Header/><main className="assistant-page">
    <div className="assistant-heading"><span className="eyebrow">PERSONALIZED SKINCARE GUIDANCE</span><h1>Ask DermaSphere AI</h1><p>Tell us what you’re looking for. Recommendations are drawn from approved, in-stock products in our catalogue.</p></div>
    <div className="assistant-layout"><section className="assistant-chat-panel">
      <div className="assistant-message assistant-welcome"><span className="assistant-avatar" aria-hidden="true">✿</span><div><b>DermaSphere Assistant</b><p>I can help you explore ingredients, build a routine, or find products using your skin preferences and budget.</p></div></div>
      {!answer&&!restoredConversation&&<fieldset className="assistant-concerns"><legend>Try asking</legend>{promptSuggestions.map((suggestion)=><button className="button outline" key={suggestion} type="button" onClick={()=>setQuery(suggestion)}>{suggestion}</button>)}</fieldset>}
      {(answer||restoredConversation)&&<><div className="assistant-message assistant-user-message"><span className="assistant-avatar" aria-hidden="true">You</span><div><b>Your question</b><p>{restoredConversation?.query??query}</p></div></div><div className="assistant-message"><span className="assistant-avatar" aria-hidden="true">✿</span><div><b>DermaSphere Assistant</b><p>{answer?.response??restoredConversation?.response}</p></div></div>{answer&&answer.recommendations.length>0&&<div className="assistant-recommendations"><h2>Recommended for you</h2><div className="assistant-product-list">{answer.recommendations.map((product)=><SuggestedProductCard key={product.id} product={product}/>)}</div></div>}{restoredConversation&&restoredConversation.recommendations.length>0&&<div className="assistant-recommendations"><h2>Previously recommended</h2><div className="assistant-product-list">{restoredConversation.recommendations.map((product)=><article className="assistant-product" key={product.product_id}><Link href={`/products/${product.product_id}`}><span className="assistant-product-placeholder">✿</span></Link><div><h3><Link href={`/products/${product.product_id}`}>{product.product_name}</Link></h3><p>{product.reason}</p></div></article>)}</div></div>}</>}
      {error&&<p className="form-error" role="alert">{error}</p>}
      <form className="assistant-form" onSubmit={ask}><label htmlFor="assistant-query">What would you like help with?</label><textarea id="assistant-query" value={query} onChange={(event)=>setQuery(event.target.value)} minLength={2} maxLength={4000} required placeholder="For example: suggest a gentle moisturizer under $30 for dry skin"/><div className="assistant-filters"><label>Skin type<select name="skin_type_id" defaultValue=""><option value="">Use my profile</option>{skinTypes.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Product category<select name="category_id" defaultValue=""><option value="">Any category</option>{categories.map((item)=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label>Maximum budget<input name="budget" type="number" min="0" step="0.01" placeholder="Any budget"/></label></div><fieldset className="assistant-concerns"><legend>Skin concerns</legend>{concerns.map((item)=><label key={item.id}><input type="checkbox" name="concerns" value={item.id}/>{item.name}</label>)}</fieldset><button className="button primary" type="submit" disabled={busy}>{busy?"Finding helpful options…":"Get guidance"}</button></form>
      <p className="assistant-disclaimer">General skincare information only. DermaSphere AI does not diagnose conditions or replace advice from a qualified dermatologist. Seek professional care for serious or persistent skin concerns.</p>
    </section><aside className="assistant-history"><div className="assistant-history-heading"><span className="eyebrow">YOUR SAVED CHATS</span><h2>Recent conversations</h2></div>{history.length?history.map((entry)=><button type="button" key={entry.id} className="assistant-history-item" aria-pressed={restoredConversation?.id===entry.id} onClick={()=>{setRestoredConversation(entry);setAnswer(null);setQuery(entry.query);setError("");}}><small>{new Date(entry.created_at).toLocaleDateString()}</small><h3>{entry.query}</h3><p>{entry.recommendations.length} product{entry.recommendations.length===1?"":"s"} recommended</p></button>):<p className="empty-state">Your saved conversations will appear here.</p>}</aside></div>
  </main></ProtectedPage>;
}
