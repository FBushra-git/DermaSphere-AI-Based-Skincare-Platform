"use client";
import {useState} from "react";
import {apiRequest} from "@/lib/api";

export type CatalogProduct={id:string;name:string;brand:string;description:string;price:string|number;image_url:string|null;average_rating:number;review_count:number;available_quantity:number;status?:string};
const price=(value:string|number)=>"$"+Number(value).toFixed(2);

function ProductCard({item}:{item:CatalogProduct}){
 const[notice,setNotice]=useState("");const[saved,setSaved]=useState(false);
 async function act(action:"cart"|"wishlist"){try{if(action==="cart")await apiRequest("/api/cart/items",{method:"POST",body:JSON.stringify({product_id:item.id,quantity:1})});else if(saved){await apiRequest("/api/wishlist/"+item.id,{method:"DELETE"});setSaved(false);}else{await apiRequest("/api/wishlist/"+item.id,{method:"POST"});setSaved(true);}setNotice(action==="cart"?"Added to bag.":saved?"Removed from wishlist.":"Saved to wishlist.");}catch(e){setNotice(e instanceof Error?e.message:"Sign in to save products.");}}
 return <article className="product-card"><a className="product-image live-product-image" href={"/products/"+item.id}>{item.image_url?<img src={item.image_url} alt={item.name}/>:<div className="product-illustration dropper" aria-hidden="true"><span className="product-cap-shape"/><span className="product-glass"><span className="pack-logo">{item.brand}</span><span className="pack-name">{item.name}</span></span></div>}<span className="stock-label">{item.available_quantity} in stock</span></a><div className="product-details"><span className="product-brand">{item.brand}</span><h3><a href={"/products/"+item.id}>{item.name}</a></h3><div className="rating" aria-label={item.average_rating+" out of 5 stars"}>★★★★★ <span>{item.average_rating?item.average_rating.toFixed(1):"New"} <small>({item.review_count})</small></span></div><div className="product-buy"><b>{price(item.price)}</b><span className="stock">● Available</span></div><div className="live-product-actions"><button className="button primary add-button" onClick={()=>act("cart")}>Add to bag</button><button className={saved?"live-wishlist is-saved":"live-wishlist"} onClick={()=>act("wishlist")} aria-label={saved?"Remove from wishlist":"Save to wishlist"}>{saved?"♥":"♡"}</button></div>{notice&&<small className="card-notice" role="status">{notice}</small>}</div></article>;
}
export function ProductGrid({items}:{items:CatalogProduct[]}){return <div className="product-grid">{items.map(item=><ProductCard key={item.id} item={item}/>)}</div>;}
