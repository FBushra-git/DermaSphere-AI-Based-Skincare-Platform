"use client";
import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/components/AuthProvider";
import { apiRequest } from "@/lib/api";

const links = [
  ["Shop", "/products"],
  ["Skin concerns", "/products"],
  ["Routines", "/customer/routines"],
  ["Ingredients", "/ingredients"],
  ["Learn", "/learn"],
];

export function Header() {
  const [open, setOpen] = useState(false);
  const [cartCount, setCartCount] = useState(0);
  const { user, logout } = useAuth();

  useEffect(() => {
    if (user?.role === "customer") {
      apiRequest<{ items: { quantity: number }[] }>("/api/cart")
        .then(({ items }) => setCartCount(items.reduce((total, item) => total + item.quantity, 0)))
        .catch(() => setCartCount(0));
    } else {
      setCartCount(0);
    }
  }, [user]);

  function submitSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const query = String(form.get("q") ?? "").trim();
    window.location.assign(query ? `/products?q=${encodeURIComponent(query)}` : "/products");
  }

  const accountHref = user
    ? user.role === "admin"
      ? "/admin"
      : user.role === "seller"
        ? "/seller"
        : "/customer"
    : "/login";

  return (
    <>
      <div className="announcement">
        A little care goes a long way <span aria-hidden="true">✳</span> Free delivery on orders over $50
      </div>
      <header className="site-header">
        <Link className="wordmark" href="/" aria-label="DermaSphere home">
          <i aria-hidden="true">✿</i> Derma<strong>Sphere</strong>
        </Link>
        <button className="menu-toggle" onClick={() => setOpen(!open)} aria-expanded={open} aria-label="Toggle navigation">
          {open ? "×" : "☰"}
        </button>
        <nav className={open ? "main-nav is-open" : "main-nav"} aria-label="Main navigation">
          {links.map(([name, href]) => (
            <Link href={href} key={name} onClick={() => setOpen(false)}>{name}</Link>
          ))}
        </nav>
        <form className="search-box" onSubmit={submitSearch} role="search">
          <label className="sr-only" htmlFor="search">Search products and ingredients</label>
          <input id="search" name="q" placeholder="Search products, ingredients..." />
          <button type="submit" aria-label="Search">⌕</button>
        </form>
        <div className="header-actions">
          <Link href={accountHref} aria-label={user ? "Your dashboard" : "Sign in"}>♙</Link>
          <Link href={user?.role === "customer" ? "/wishlist" : "/login"} aria-label="Wishlist">♡</Link>
          <Link href={user?.role === "customer" ? "/cart" : "/login"} aria-label={`Shopping bag, ${cartCount} items`}>
            ♧<small>{cartCount}</small>
          </Link>
          <Link className="ai-link" href={user ? "/assistant" : "/login"}>✳ &nbsp;Ask DermaSphere AI</Link>
          {user ? (
            <button className="header-signout" onClick={logout} aria-label="Sign out">↪</button>
          ) : (
            <Link className="header-signin" href="/login">Sign in</Link>
          )}
        </div>
      </header>
    </>
  );
}
