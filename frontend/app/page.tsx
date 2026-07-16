"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("eap_access_token") : null;
    router.replace(token ? "/dashboard" : "/login");
  }, [router]);
  return null;
}
