import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {title:"DermaSphere — Your skin, your routine",description:"Thoughtful skincare, clear ingredient information, and routines that fit your skin."};
export default function RootLayout({children}:Readonly<{children:React.ReactNode}>){return <html lang="en"><body>{children}</body></html>}