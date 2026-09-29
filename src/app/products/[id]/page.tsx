"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Header } from "@/components/Header";
import { Footer } from "@/components/Footer";
import { useAuth } from "@/components/AuthProvider";
import { apiRequest } from "@/lib/api";

type Product = {
  id: string; name: string; brand: string; description: string; price: string | number;
  image_url: string | null; benefits: string | null; usage_instructions: string | null;
  cautions: string | null; available_quantity: number; average_rating: number;
  review_count: number; seller: { store_name: string; name: string } | null;
  category: string | null; ingredients: { id: string; name: string; description: string | null; benefits: string | null; cautions: string | null }[];
  suitable_skin_types: string[]; suitable_concerns: string[];
};
type Review = { id: string; name: string; rating: number; body: string | null; created_at: string };
const money = (value: string | number) => `$${Number(value).toFixed(2)}`;

export default function ProductDetailsPage() {
  const { id } = useParams<{ id: string }>();
  const { user } = useAuth();
  const [product, setProduct] = useState<Product | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [tab, setTab] = useState("Description");
  const [quantity, setQuantity] = useState(1);
  const [notice, setNotice] = useState("");
  const loadReviews = useCallback(() => apiRequest<Review[]>(`/api/products/${id}/reviews`).then(setReviews), [id]);
  useEffect(() => {
    apiRequest<Product>(`/api/products/${id}`).then(setProduct).catch((e: Error) => setNotice(e.message));
    void loadReviews().catch(() => setReviews([]));
  }, [id, loadReviews]);

  async function action(kind: "cart" | "wishlist") {
    if (!product) return;
    try {
      if (kind === "cart") await apiRequest("/api/cart/items", { method: "POST", body: JSON.stringify({ product_id: product.id, quantity }) });
      else await apiRequest(`/api/wishlist/${product.id}`, { method: "POST" });
      setNotice(kind === "cart" ? "Added to your bag." : "Saved to your wishlist.");
    } catch (e) { setNotice(e instanceof Error ? e.message : "Sign in to continue."); }
  }
  async function submitReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!product) return;
    const form = event.currentTarget;
    const values = new FormData(form);
    try {
      await apiRequest(`/api/products/${product.id}/reviews`, { method: "POST", body: JSON.stringify({ rating: Number(values.get("rating")), body: String(values.get("body") || "") || null }) });
      form.reset(); setNotice("Your review was submitted."); await loadReviews();
      const updated = await apiRequest<Product>(`/api/products/${product.id}`); setProduct(updated);
    } catch (e) { setNotice(e instanceof Error ? e.message : "Reviews are available after delivery. You can submit one review per product."); }
  }
  async function reportReview(review: Review) {
    try { await apiRequest(`/api/reviews/${review.id}/report`, { method: "POST" }); setNotice("Thank you. The review was reported for admin review."); await loadReviews(); }
    catch (e) { setNotice(e instanceof Error ? e.message : "Could not report this review."); }
  }

  if (!product) return <><Header/><main className="detail-page">{notice ? <p className="empty-state" role="alert">{notice}</p> : <p className="empty-state">Loading product…</p>}</main><Footer/></>;
  const tabs = ["Description", "Ingredients", "Benefits", "How to use", "Cautions", "Reviews"];
  return <><Header/><main className="detail-page"><div className="breadcrumbs"><a href="/">Home</a> / <a href="/products">Shop</a> / {product.category || "Skincare"} / {product.name}</div>
    <section className="detail-main"><div className="detail-gallery"><div className="detail-image">{product.image_url ? <img src={product.image_url} alt={product.name}/> : <div className="detail-product-art"><span>{product.brand}</span><b>{product.name}</b></div>}</div></div><div className="detail-info"><span className="eyebrow">{product.brand}</span><h1>{product.name}</h1><div className="detail-rating" aria-label={`${product.average_rating} out of 5 stars`}>★★★★★ <span>{product.average_rating ? product.average_rating.toFixed(1) : "New"} ({product.review_count} reviews)</span></div><div className="detail-price">{money(product.price)} <span>{product.available_quantity > 0 ? `${product.available_quantity} in stock` : "Out of stock"}</span></div><p className="detail-description">{product.description}</p><div className="suitability"><div><b>Suitable skin types</b><span>{product.suitable_skin_types.join(", ") || "See product description"}</span></div><div><b>Skin concerns</b><span>{product.suitable_concerns.join(", ") || "Everyday care"}</span></div></div><label className="quantity-picker">Quantity <input type="number" min="1" max={Math.min(99, product.available_quantity)} value={quantity} onChange={(e) => setQuantity(Number(e.target.value))}/></label><div className="detail-actions"><button className="button primary" disabled={!product.available_quantity} onClick={() => void action("cart")}>Add to cart</button><button className="button outline" onClick={() => void action("wishlist")}>♡ Wishlist</button></div>{notice && <p className="dashboard-notice" role="status">{notice}</p>}<p className="seller-note">Sold by {product.seller?.store_name || product.brand}. Product listing reviewed by DermaSphere.</p></div></section>
    <div className="detail-tabs" role="tablist">{tabs.map((item) => <button role="tab" aria-selected={tab === item} className={tab === item ? "active" : ""} key={item} onClick={() => setTab(item)}>{item}</button>)}</div>
    <section className="detail-tab-content">{tab === "Description" && <p>{product.description}</p>}{tab === "Ingredients" && (product.ingredients.length ? <div className="ingredient-cards">{product.ingredients.map((ingredient) => <article key={ingredient.id}><h3>{ingredient.name}</h3><p>{ingredient.description}</p><small>{ingredient.benefits}</small>{ingredient.cautions && <p className="muted-copy">Cautions: {ingredient.cautions}</p>}</article>)}</div> : <p>Ingredient information has not been provided.</p>)}{tab === "Benefits" && <p>{product.benefits || "See the product label for details."}</p>}{tab === "How to use" && <p>{product.usage_instructions || "Follow the usage directions on the product label."}</p>}{tab === "Cautions" && <p>{product.cautions || "Follow the product label and patch-test new skincare as appropriate."}</p>}{tab === "Reviews" && <div className="reviews-section">{reviews.length ? reviews.map((review) => <article className="review-row" key={review.id}><div className="review-heading"><b>{review.name}</b><span aria-label={`${review.rating} out of 5 stars`}>{"★".repeat(review.rating)}{"☆".repeat(5 - review.rating)} <small>{review.rating}/5</small></span></div><p>{review.body || "Verified product review."}</p><div className="review-footer"><small>{new Date(review.created_at).toLocaleDateString()}</small>{user?.role === "customer" && <button className="text-button" type="button" onClick={() => void reportReview(review)}>Report review</button>}</div></article>) : <p>No customer reviews yet.</p>}{user?.role === "customer" && <form className="review-form" onSubmit={submitReview}><h3>Share your experience</h3><p>Reviews are available after your order is delivered. You may submit one review for each product you have purchased.</p><label>Rating<select name="rating" defaultValue="5">{[5, 4, 3, 2, 1].map((rating) => <option key={rating} value={rating}>{rating} out of 5</option>)}</select></label><label>Your review<textarea name="body" maxLength={5000} rows={4} placeholder="What would you like other customers to know?"/></label><button className="button primary" type="submit">Submit review</button></form>}{!user && <p><a href="/login">Sign in</a> to submit a review after delivery.</p>}</div>}</section>
  </main><Footer/></>;
}
