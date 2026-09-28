"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { DashboardFrame } from "@/components/DashboardFrame";
import { ProtectedPage } from "@/components/ProtectedPage";
import { Header } from "@/components/Header";
import { apiRequest } from "@/lib/api";

type RoutineProduct = { id: string; name: string; brand: string; image_url: string | null; sequence: number; step_note: string | null };
type Routine = { id: string; name: string; description: string | null; routine_type: "morning" | "evening" | "custom"; products: RoutineProduct[] };
type Product = { id: string; name: string; brand: string };
const navigation = [
  { label: "Overview", href: "/customer", icon: "⌂" },
  { label: "My routines", href: "/customer/routines", icon: "☼" },
  { label: "Wishlist", href: "/wishlist", icon: "♡" },
  { label: "My orders", href: "/customer/orders", icon: "▤" },
];

export default function CustomerRoutinesPage() {
  const [routines, setRoutines] = useState<Routine[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    try {
      const [routineRows, catalog] = await Promise.all([
        apiRequest<Routine[]>("/api/routines"),
        apiRequest<{ items: Product[] }>("/api/products?page_size=100"),
      ]);
      setRoutines(routineRows);
      setProducts(catalog.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not load routines.");
    }
  }, []);
  useEffect(() => { void load(); }, [load]);

  async function createRoutine(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    try {
      await apiRequest("/api/routines", {
        method: "POST",
        body: JSON.stringify({ name: form.get("name"), routine_type: form.get("routine_type"), description: form.get("description") || null }),
      });
      event.currentTarget.reset();
      setNotice("Your routine is ready.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not create this routine.");
    }
  }

  async function editRoutine(routine: Routine, form: HTMLFormElement) {
    const values = new FormData(form);
    try {
      await apiRequest(`/api/routines/${routine.id}`, {
        method: "PATCH",
        body: JSON.stringify({ name: values.get("name"), routine_type: values.get("routine_type"), description: values.get("description") || null }),
      });
      setNotice("Routine details saved.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not save routine details.");
    }
  }

  async function addProduct(routine: Routine, form: HTMLFormElement) {
    const values = new FormData(form);
    const productId = String(values.get("product_id") || "");
    if (!productId) return;
    try {
      await apiRequest(`/api/routines/${routine.id}/products`, {
        method: "POST",
        body: JSON.stringify({ product_id: productId, sequence: routine.products.length + 1 }),
      });
      form.reset();
      setNotice("Product added to your routine.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not add this product.");
    }
  }

  async function moveProduct(routine: Routine, product: RoutineProduct, direction: -1 | 1) {
    const ordered = [...routine.products].sort((a, b) => a.sequence - b.sequence);
    const index = ordered.findIndex((item) => item.id === product.id);
    const target = index + direction;
    if (target < 0 || target >= ordered.length) return;
    const neighbor = ordered[target];
    try {
      await apiRequest(`/api/routines/${routine.id}/products/${product.id}`, {
        method: "PATCH",
        body: JSON.stringify({ product_id: product.id, sequence: neighbor.sequence, step_note: product.step_note }),
      });
      await apiRequest(`/api/routines/${routine.id}/products/${neighbor.id}`, {
        method: "PATCH",
        body: JSON.stringify({ product_id: neighbor.id, sequence: product.sequence, step_note: neighbor.step_note }),
      });
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not reorder routine steps.");
    }
  }

  async function removeProduct(routine: Routine, productId: string) {
    try {
      await apiRequest(`/api/routines/${routine.id}/products/${productId}`, { method: "DELETE" });
      setNotice("Product removed from routine.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not remove product.");
    }
  }

  async function deleteRoutine(routine: Routine) {
    if (!window.confirm(`Delete “${routine.name}”?`)) return;
    try {
      await apiRequest(`/api/routines/${routine.id}`, { method: "DELETE" });
      setNotice("Routine deleted.");
      await load();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Could not delete routine.");
    }
  }

  return <ProtectedPage role="customer"><Header/><DashboardFrame eyebrow="YOUR SPACE" title="Skincare routines" nav={navigation}>
    <section className="routine-create-panel">
      <div><span className="eyebrow">BUILD YOUR RITUAL</span><h2>Create a routine</h2><p>Organize products into a morning, evening, or custom sequence.</p></div>
      <form className="routine-create-form" onSubmit={createRoutine}>
        <label>Routine name<input name="name" minLength={2} maxLength={120} required placeholder="My morning routine" /></label>
        <label>Routine type<select name="routine_type" defaultValue="morning"><option value="morning">Morning</option><option value="evening">Evening</option><option value="custom">Custom</option></select></label>
        <label className="routine-description-field">Description<textarea name="description" rows={2} placeholder="What do you want this routine to help with?" /></label>
        <button className="button primary" type="submit">Create routine</button>
      </form>
    </section>
    {notice && <p className="inline-notice" role="status">{notice}</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="routine-list" aria-label="Saved routines">
      {routines.map((routine) => <article className="routine-card" key={routine.id}>
        <form className="routine-edit-form" onSubmit={(event) => { event.preventDefault(); void editRoutine(routine, event.currentTarget); }}>
          <div className="routine-card-heading"><span className={`routine-icon routine-${routine.routine_type}`}>{routine.routine_type === "morning" ? "☀" : routine.routine_type === "evening" ? "☾" : "✿"}</span><span className="eyebrow">{routine.routine_type} ritual</span></div>
          <label>Routine name<input name="name" required minLength={2} maxLength={120} defaultValue={routine.name} /></label>
          <label>Routine type<select name="routine_type" defaultValue={routine.routine_type}><option value="morning">Morning</option><option value="evening">Evening</option><option value="custom">Custom</option></select></label>
          <label>Description<textarea name="description" rows={2} defaultValue={routine.description ?? ""} /></label>
          <div className="routine-form-actions"><button className="button outline" type="submit">Save details</button><button className="text-button" type="button" onClick={() => void deleteRoutine(routine)}>Delete routine</button></div>
        </form>
        <div className="routine-steps"><h3>Product steps <span>({routine.products.length})</span></h3>
          {routine.products.length ? <ol>{[...routine.products].sort((a, b) => a.sequence - b.sequence).map((product, index) => <li key={product.id}><span className="step-number">{index + 1}</span><div className="step-description"><Link href={`/products/${product.id}`}>{product.name}</Link><small>{product.brand}</small></div><div className="step-actions"><button type="button" aria-label={`Move ${product.name} earlier`} disabled={index === 0} onClick={() => void moveProduct(routine, product, -1)}>↑</button><button type="button" aria-label={`Move ${product.name} later`} disabled={index === routine.products.length - 1} onClick={() => void moveProduct(routine, product, 1)}>↓</button><button type="button" aria-label={`Remove ${product.name}`} onClick={() => void removeProduct(routine, product.id)}>×</button></div></li>)}</ol> : <p className="empty-state">Add approved products to make this routine actionable.</p>}
          <form className="routine-add-product" onSubmit={(event) => { event.preventDefault(); void addProduct(routine, event.currentTarget); }}><label htmlFor={`product-${routine.id}`}>Add a product</label><select id={`product-${routine.id}`} name="product_id" required defaultValue=""><option value="" disabled>Select an approved product</option>{products.filter((product) => !routine.products.some((item) => item.id === product.id)).map((product) => <option key={product.id} value={product.id}>{product.brand} — {product.name}</option>)}</select><button className="button primary" type="submit">Add step</button></form>
        </div>
      </article>)}
      {!routines.length && !error && <div className="shop-empty"><span aria-hidden="true">☼</span><h2>Your routines start here</h2><p>Create a routine above, then arrange products into the order you use them.</p><Link className="button outline" href="/products">Browse products</Link></div>}
    </section>
  </DashboardFrame></ProtectedPage>;
}
