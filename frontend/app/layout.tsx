import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "@/globals.css";
import { UserProvider } from "@/context/UserContext";
import { Toaster } from "react-hot-toast";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
    title: "Research Helper",
    description: "Chat with your documents and the web",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className={inter.className}>
                <UserProvider>
                    {children}
                    <Toaster position="top-center" />
                </UserProvider>
            </body>
        </html>
    );
}