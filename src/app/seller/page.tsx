"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ProtectedPage } from "@/components/ProtectedPage";
import { DashboardFrame, StatCards } from "@/components/DashboardFrame";
import { apiRequest } from "@/lib/api";

type Option = { id: string; name: string };
type Product = {
  id: string; name: string; brand: string; description: string; price: string; status: string;
  available_quantity: number; image_url: string | null; benefits: string | null;
  usage_instructions: string | null; cautions: string | null; category_id: string | null;
  ingredient_ids: string[]; skin_type_ids: string[]; skin_concern_ids: string[];
};
type OrderLine = { order_id: string; product_id: string; product_name: string; quantity: number; status: string; line_total: string; created_at: string; can_manage_order: boolean };
type SellerOrder = { order_id: string; status: string; lines: OrderLine[]; total: number; created_at: string; can_manage_order: boolean };
type Sales = { products: number; orders: number; total_sales: string };
type ProductDraft = Omit<Product, "id" | "status" | "available_quantity">;
const money = (value: unknown) => `$${Number(value).toFixed(2)}`;
const navigation = [
  { label: "Overview", href: "/seller", icon: "⌂" },
  { label: "My products", href: "/seller#products", icon: "▦" },
  { label: "Add product", href: "/seller#add-product", icon: "＋" },
  { label: "Orders", href: "/seller#orders", icon: "▤" },
  { label: "Sales report", href: "/seller#sales", icon: "▥" },
  { label: "Store profile", href: "/seller/profile", icon: "settings" },
];
const emptyDraft: ProductDraft = {
  name: "", brand: "", description: "", price: "", image_url: "", benefits: "",
  usage_instructions: "", cautions: "", category_id: "", ingredient_ids: [],
  skin_type_ids: [], skin_concern_ids: [],
};

function groupOrders(lines: OrderLine[]): SellerOrder[] {
  const grouped = new Map<string, SellerOrder>();
  for (const line of lines) {
    const order = grouped.get(line.order_id) ?? {
      order_id: line.order_id, status: line.status, lines: [], total: 0,
      created_at: line.created_at, can_manage_order: line.can_manage_order,
    };
    order.lines.push(line);
    order.total += Number(line.line_total);
    grouped.set(line.order_id, order);
  }
  return [...grouped.values()];
}
function ProductFields({ draft, setDraft, categories, ingredients, skinTypes, concerns }: {
  draft: ProductDraft; setDraft: (draft: ProductDraft) => void; categories: Option[];
  ingredients: Option[]; skinTypes: Option[]; concerns: Option[];
}) {
  function choices(field: "ingredient_ids" | "skin_type_ids" | "skin_concern_ids", values: string[]) {
    setDraft({ ...draft, [field]: values });
  }
  return <>
    <label>Product name<input required minLength={2} maxLength={180} value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></label>
    <label>Brand<input required maxLength={120} value={draft.brand} onChange={(e) => setDraft({ ...draft, brand: e.target.value })} /></label>
    <label>Category<select value={draft.category_id ?? ""} onChange={(e) => setDraft({ ...draft, category_id: e.target.value || null })}><option value="">Choose category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <label>Price<input required type="number" min="0" step="0.01" value={draft.price} onChange={(e) => setDraft({ ...draft, price: e.target.value })} /></label>
    <label>Image URL<input type="url" value={draft.image_url ?? ""} onChange={(e) => setDraft({ ...draft, image_url: e.target.value || null })} placeholder="https://…" /></label>
    <label className="full-field">Description<textarea required minLength={10} rows={3} value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></label>
    <label>Benefits<textarea rows={2} value={draft.benefits ?? ""} onChange={(e) => setDraft({ ...draft, benefits: e.target.value || null })} /></label>
    <label>How to use<textarea rows={2} value={draft.usage_instructions ?? ""} onChange={(e) => setDraft({ ...draft, usage_instructions: e.target.value || null })} /></label>
    <label>Cautions<textarea rows={2} value={draft.cautions ?? ""} onChange={(e) => setDraft({ ...draft, cautions: e.target.value || null })} /></label>
    <label>Ingredients<select multiple value={draft.ingredient_ids} onChange={(e) => choices("ingredient_ids", [...e.target.selectedOptions].map((option) => option.value))}>{ingredients.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><small>Use Ctrl or Cmd to select multiple.</small></label>
    <label>Suitable skin types<select multiple value={draft.skin_type_ids} onChange={(e) => choices("skin_type_ids", [...e.target.selectedOptions].map((option) => option.value))}>{skinTypes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
    <label>Suitable concerns<select multiple value={draft.skin_concern_ids} onChange={(e) => choices("skin_concern_ids", [...e.target.selectedOptions].map((option) => option.value))}>{concerns.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
  </>;
}

export default function SellerDashboard() {
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<SellerOrder[]>([]);
  const [sales, setSales] = useState<Sales>({ products: 0, orders: 0, total_sales: "0" });
  const [categories, setCategories] = useState<Option[]>([]);
  const [ingredients, setIngredients] = useState<Option[]>([]);
  const [skinTypes, setSkinTypes] = useState<Option[]>([]);
  const [concerns, setConcerns] = useState<Option[]>([]);
  const [draft, setDraft] = useState<ProductDraft>(emptyDraft);
  const [editing, setEditing] = useState<string | null>(null);
  const [stockDraft, setStockDraft] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [productRows, orderLines, summary, categoryRows, ingredientRows, types, skinConcerns] = await Promise.all([
        apiRequest<Product[]>("/api/seller/products"), apiRequest<OrderLine[]>("/api/seller/orders"),
        apiRequest<Sales>("/api/seller/reports/sales"), apiRequest<Option[]>("/api/categories"),
        apiRequest<Option[]>("/api/ingredients"), apiRequest<Option[]>("/api/skin-types"),
        apiRequest<Option[]>("/api/skin-concerns"),
      ]);
      setProducts(productRows); setOrders(groupOrders(orderLines)); setSales(summary);
      setCategories(categoryRows); setIngredients(ingredientRows); setSkinTypes(types); setConcerns(skinConcerns);
      setError("");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not load your store."); }
  }
  useEffect(() => { void load(); }, []);

  function makePayload(form: FormData, includeStock: boolean) {
    return {
      name: draft.name, brand: draft.brand, description: draft.description,
      price: draft.price, category_id: draft.category_id || null,
      image_url: draft.image_url || null, benefits: draft.benefits || null,
      usage_instructions: draft.usage_instructions || null,
      cautions: draft.cautions || null, ingredient_ids: draft.ingredient_ids,
      skin_type_ids: draft.skin_type_ids, skin_concern_ids: draft.skin_concern_ids,
      ...(includeStock ? { stock_quantity: Number(form.get("stock_quantity")) } : {}),
    };
  }
  async function submitProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await apiRequest("/api/products", { method: "POST", body: JSON.stringify(makePayload(new FormData(event.currentTarget), true)) });
      event.currentTarget.reset(); setDraft(emptyDraft); setNotice("Product submitted for admin review."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not submit the product."); }
    finally { setBusy(false); }
  }
  function beginEdit(product: Product) {
    setEditing(product.id);
    setDraft({ name: product.name, brand: product.brand, description: product.description, price: product.price,
      image_url: product.image_url, benefits: product.benefits, usage_instructions: product.usage_instructions,
      cautions: product.cautions, category_id: product.category_id, ingredient_ids: product.ingredient_ids,
      skin_type_ids: product.skin_type_ids, skin_concern_ids: product.skin_concern_ids });
    document.getElementById("product-editor")?.scrollIntoView({ behavior: "smooth" });
  }
  async function saveProduct(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!editing) return; setBusy(true); setError("");
    try {
      await apiRequest(`/api/seller/products/${editing}`, { method: "PATCH", body: JSON.stringify(makePayload(new FormData(event.currentTarget), false)) });
      setEditing(null); setDraft(emptyDraft); setNotice("Product changes saved and sent to admin review."); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save this product."); }
    finally { setBusy(false); }
  }
  async function updateStock(product: Product) {
    const quantity = Number(stockDraft[product.id] ?? product.available_quantity);
    if (!Number.isInteger(quantity) || quantity < 0) { setError("Stock must be a non-negative whole number."); return; }
    try {
      await apiRequest(`/api/seller/products/${product.id}/inventory`, { method: "PUT", body: JSON.stringify({ available_quantity: quantity }) });
      setNotice(`Stock updated for ${product.name}.`); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update stock."); }
  }
  async function advanceOrder(order: SellerOrder) {
    const next: Record<string, string> = { pending: "confirmed", confirmed: "processing", processing: "shipped", shipped: "delivered" };
    const status = next[order.status.toLowerCase()]; if (!status) return;
    try {
      await apiRequest(`/api/seller/orders/${order.order_id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
      setNotice(`Order ${order.order_id.slice(0, 8)} updated to ${status}.`); await load();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not update this order."); }
  }
  const pendingCount = useMemo(() => products.filter((product) => product.status === "pending").length, [products]);

  return <ProtectedPage role="seller"><DashboardFrame eyebrow="SELLER STUDIO" title="Your store at a glance" nav={navigation}>
    <div className="dashboard-welcome"><div><span className="eyebrow">SELLER OVERVIEW</span><h2>Your good work, growing.</h2><p>Keep your products, stock, and orders in one place.</p></div><a className="button primary" href="#add-product">Add product +</a></div>
    {notice&&<p className="inline-notice" role="status">{notice}</p>}{error&&<p className="form-error" role="alert">{error}</p>}
    <StatCards items={[{label:"Products",value:sales.products,icon:"▦"},{label:"Orders",value:sales.orders,icon:"▤"},{label:"Sales",value:money(sales.total_sales),icon:"▥"},{label:"Pending review",value:pendingCount,icon:"◷"}]}/>
    <section className="dashboard-panel" id="products"><span className="eyebrow">YOUR CATALOGUE</span><h2>My products</h2><div className="table-scroll"><table className="data-table"><thead><tr><th>Product</th><th>Price</th><th>Stock</th><th>Approval</th><th>Inventory</th><th>Details</th></tr></thead><tbody>{products.map((product)=><tr key={product.id}><td><b>{product.name}</b><small>{product.brand}</small></td><td>{money(product.price)}</td><td>{product.available_quantity}</td><td><span className={`status-pill status-${product.status}`}>{product.status}</span></td><td><div className="seller-stock-editor"><input aria-label={`Available quantity for ${product.name}`} type="number" min="0" value={stockDraft[product.id]??product.available_quantity} onChange={(e)=>setStockDraft({...stockDraft,[product.id]:e.target.value})}/><button className="table-action" type="button" onClick={()=>void updateStock(product)}>Save</button></div></td><td><button className="table-action" type="button" onClick={()=>beginEdit(product)} disabled={product.status==="archived"}>Edit</button></td></tr>)}</tbody></table></div>{!products.length&&<p className="empty-state">Products you submit will appear here.</p>}</section>
    <div className="dashboard-columns"><section className="dashboard-panel" id="orders"><span className="eyebrow">FULFILMENT · {orders.length}</span><h2>Seller orders</h2>{orders.map((order)=><article className="seller-order-card" key={order.order_id}><div className="seller-order-heading"><span><b>Order #{order.order_id.slice(0,8)}</b><small>{new Date(order.created_at).toLocaleDateString()}</small></span><span className={`status-pill status-${order.status.toLowerCase()}`}>{order.status}</span></div>{order.lines.map((line)=><div className="data-row" key={line.product_id}><span><b>{line.product_name}</b><small>Qty {line.quantity}</small></span><b>{money(line.line_total)}</b></div>)}<div className="seller-order-footer"><b>Order value: {money(order.total)}</b>{order.can_manage_order&&order.status.toLowerCase()!=="delivered"&&order.status.toLowerCase()!=="cancelled"?<button className="table-action" type="button" onClick={()=>void advanceOrder(order)}>Mark {({pending:"confirmed",confirmed:"processing",processing:"shipped",shipped:"delivered"} as Record<string,string>)[order.status.toLowerCase()]??"next"}</button>:!order.can_manage_order?<small>Order contains products from multiple sellers. Order status is managed by the platform.</small>:null}</div></article>)}{!orders.length&&<p className="empty-state">Orders containing your products will appear here.</p>}</section><section className="dashboard-panel" id="sales"><span className="eyebrow">STORE PERFORMANCE</span><h2>Sales overview</h2><div className="sales-total">{money(sales.total_sales)}</div><p className="muted-copy">Sales from non-cancelled orders.</p><p><b>{sales.orders}</b> orders across <b>{sales.products}</b> products</p></section></div>
    <section className="dashboard-panel" id="product-editor"><span className="eyebrow">{editing?"UPDATE A LISTING":"GROW YOUR CATALOGUE"}</span><h2>{editing?"Edit product":"Submit a product"}</h2><form className="product-form" onSubmit={editing?saveProduct:submitProduct}><ProductFields draft={draft} setDraft={setDraft} categories={categories} ingredients={ingredients} skinTypes={skinTypes} concerns={concerns}/>{!editing&&<label>Initial stock<input name="stock_quantity" type="number" min="0" defaultValue="0" required/></label>}<div className="product-form-actions"><button className="button primary" type="submit" disabled={busy}>{busy?"Saving…":editing?"Save changes for review":"Submit for approval"}</button>{editing&&<button className="button outline" type="button" onClick={()=>{setEditing(null);setDraft(emptyDraft);}}>Cancel</button>}</div></form></section>
  </DashboardFrame></ProtectedPage>;
}
