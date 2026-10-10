import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // تحديد المجلد الجذر لـ Turbopack لتجنب تحذير الـ lockfiles المتعددة
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
