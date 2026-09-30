"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { apiRequest } from "@/lib/api";
type Account = { id: string; name: string; email: string; role: "customer" | "seller" | "admin" };
type Signup = { name: string; email: string; password: string; role: "customer" | "seller"; store_name?: string };
type AuthContextValue = { user: Account | null; ready: boolean; login: (email: string, password: string) => Promise<Account>; register: (payload: Signup) => Promise<Account>; logout: () => void };
const AuthContext = createContext<AuthContextValue | null>(null);
export function AuthProvider({ children }: { children: React.ReactNode }) {
 const [user,setUser]=useState<Account|null>(null);const [ready,setReady]=useState(false);
 useEffect(()=>{const expireSession=()=>setUser(null);window.addEventListener("dermasphere:session-expired",expireSession);const token=window.sessionStorage.getItem("dermasphere_token");if(!token){setReady(true);return()=>window.removeEventListener("dermasphere:session-expired",expireSession);}apiRequest<Account>("/api/auth/me").then(setUser).catch(()=>window.sessionStorage.removeItem("dermasphere_token")).finally(()=>setReady(true));return()=>window.removeEventListener("dermasphere:session-expired",expireSession);},[]);
 const login=useCallback(async(email:string,password:string)=>{const result=await apiRequest<{access_token:string;user:Account}>("/api/auth/login",{method:"POST",body:JSON.stringify({email,password})});window.sessionStorage.setItem("dermasphere_token",result.access_token);setUser(result.user);return result.user;},[]);
 const register=useCallback(async(payload:Signup)=>{const result=await apiRequest<{access_token:string;user:Account}>("/api/auth/register",{method:"POST",body:JSON.stringify(payload)});window.sessionStorage.setItem("dermasphere_token",result.access_token);setUser(result.user);return result.user;},[]);
 const logout=useCallback(()=>{window.sessionStorage.removeItem("dermasphere_token");setUser(null);},[]);
 const value=useMemo(()=>({user,ready,login,register,logout}),[user,ready,login,register,logout]);
 return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth(){const context=useContext(AuthContext);if(!context)throw new Error("useAuth must be used inside AuthProvider");return context;}
